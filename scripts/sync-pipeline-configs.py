#!/usr/bin/env python3
"""
Generic Pipeline Sync Script

This script intelligently syncs Tekton pipeline configurations with upstream
while preserving local customizations like taskRef configurations and specific
parameter values.

Features:
- Compares spec fields between upstream and local pipeline
- Updates local pipeline with upstream values if mismatch found
- Skips taskRef field comparison entirely
- Preserves specific local parameter values (hermetic, build-source-image, build-args, build-platforms)
- Reports missing tasks in local pipeline
- Auto-patches missing tasks using konflux-pipeline-patcher tool
- Updates task bundle references to latest versions
- Supports multiple pipeline mappings
"""

import requests
import yaml
import json
import sys
import os
import subprocess
import tempfile
from typing import Dict, Any, List, Set

# Configuration - Pipeline mappings: upstream_url -> local_path
PIPELINE_MAPPINGS = {
    'https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/fbc-builder/fbc-builder.yaml': '.tekton/fbc-build-pipeline.yaml',
    'https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/docker-build-oci-ta/docker-build-oci-ta.yaml': '.tekton/single-arch-build-pipeline.yaml',
    'https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/docker-build-multi-platform-oci-ta/docker-build-multi-platform-oci-ta.yaml': '.tekton/multi-arch-build-pipeline.yaml',
}


def fetch_upstream_pipeline(url: str) -> Dict[str, Any]:
    """Fetch upstream pipeline YAML from GitHub."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return yaml.safe_load(response.text)
    except requests.RequestException as e:
        print(f"Error fetching upstream pipeline: {e}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing upstream YAML: {e}")
        sys.exit(1)


def load_local_pipeline(filepath: str) -> Dict[str, Any]:
    """Load local pipeline YAML file."""
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Local pipeline file not found: {filepath}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing local YAML: {e}")
        sys.exit(1)


def save_local_pipeline(filepath: str, data: Dict[str, Any]) -> None:
    """Save updated pipeline to local file."""
    try:
        with open(filepath, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)
    except Exception as e:
        print(f"Error saving local pipeline: {e}")
        sys.exit(1)


def remove_taskref_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively remove taskRef fields from pipeline data for comparison."""
    # Parameters to exclude from comparison (preserve local values)
    PRESERVE_PARAMS = {'hermetic', 'build-source-image', 'build-args', 'build-platforms'}
    
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if key == 'taskRef':
                continue  # Skip taskRef entirely
            elif key == 'params' and isinstance(value, list):
                # Filter out preserved parameters from comparison
                filtered_params = []
                for param in value:
                    if isinstance(param, dict) and param.get('name') not in PRESERVE_PARAMS:
                        filtered_params.append(remove_taskref_fields(param))
                cleaned[key] = filtered_params
            elif isinstance(value, (dict, list)):
                cleaned[key] = remove_taskref_fields(value)
            else:
                cleaned[key] = value
        return cleaned
    elif isinstance(data, list):
        return [remove_taskref_fields(item) for item in data]
    else:
        return data


def get_task_names(pipeline_spec: Dict[str, Any]) -> Set[str]:
    """Extract task names from pipeline spec."""
    task_names = set()
    
    if 'tasks' in pipeline_spec:
        for task in pipeline_spec['tasks']:
            if 'name' in task:
                task_names.add(task['name'])
    
    if 'finally' in pipeline_spec:
        for task in pipeline_spec['finally']:
            if 'name' in task:
                task_names.add(task['name'])
    
    return task_names


def download_pipeline_patcher(script_dir: str) -> str:
    """Download the konflux-pipeline-patcher tool if it doesn't exist."""
    patcher_path = os.path.join(script_dir, 'pipeline-patcher')
    
    if not os.path.exists(patcher_path):
        print("📥 Downloading konflux-pipeline-patcher tool...")
        try:
            response = requests.get('https://github.com/simonbaird/konflux-pipeline-patcher/raw/main/pipeline-patcher')
            response.raise_for_status()
            
            with open(patcher_path, 'wb') as f:
                f.write(response.content)
            
            os.chmod(patcher_path, 0o755)
            print(f"✅ Pipeline patcher downloaded to {patcher_path}")
        except Exception as e:
            print(f"❌ Error downloading pipeline patcher: {e}")
            return None
    else:
        print(f"✅ Pipeline patcher already available at {patcher_path}")
    
    return patcher_path


def get_available_tasks(patcher_path: str) -> Set[str]:
    """Get list of available tasks from pipeline-patcher."""
    try:
        result = subprocess.run([patcher_path, 'list-tasks'], 
                              capture_output=True, text=True, check=True)
        
        tasks = set()
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                tasks.add(line.strip())
        
        return tasks
    except subprocess.CalledProcessError as e:
        print(f"❌ Error getting available tasks: {e}")
        return set()


def patch_missing_tasks(patcher_path: str, pipeline_path: str, missing_tasks: Set[str]) -> bool:
    """Use pipeline-patcher to add missing tasks to the pipeline."""
    if not missing_tasks:
        return False
    
    # Get available tasks from pipeline-patcher
    available_tasks = get_available_tasks(patcher_path)
    
    # Filter missing tasks to only those available in pipeline-patcher
    patchable_tasks = missing_tasks.intersection(available_tasks)
    unpatchable_tasks = missing_tasks - available_tasks
    
    if unpatchable_tasks:
        print(f"\n⚠️  Tasks not available in pipeline-patcher:")
        for task in sorted(unpatchable_tasks):
            print(f"  - {task}")
    
    if not patchable_tasks:
        print("❌ No missing tasks can be patched automatically")
        return False
    
    print(f"\n🔧 Patching {len(patchable_tasks)} missing tasks:")
    for task in sorted(patchable_tasks):
        print(f"  - {task}")
    
    # Convert set to comma-separated string for pipeline-patcher
    task_names = ','.join(sorted(patchable_tasks))
    
    try:
        # Use pipeline-patcher to add the missing tasks
        result = subprocess.run([patcher_path, 'patch', pipeline_path, task_names], 
                              capture_output=True, text=True, check=True)
        
        print(f"✅ Successfully patched missing tasks")
        if result.stdout.strip():
            print(f"Output: {result.stdout.strip()}")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error patching tasks: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False


def update_task_bundle_refs(patcher_path: str, repo_path: str) -> bool:
    """Update task bundle references to latest versions using pipeline-patcher."""
    try:
        print("🔄 Updating task bundle references to latest versions...")
        result = subprocess.run([patcher_path, 'bump-task-refs', repo_path], 
                              capture_output=True, text=True, check=True)
        
        print("✅ Task bundle references updated successfully")
        if result.stdout.strip():
            print(f"Output: {result.stdout.strip()}")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error updating task bundle references: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False


def compare_specs(local_spec: Dict[str, Any], upstream_spec: Dict[str, Any]) -> bool:
    """Compare two pipeline specs, ignoring taskRef fields."""
    local_clean = remove_taskref_fields(local_spec)
    upstream_clean = remove_taskref_fields(upstream_spec)
    
    return json.dumps(local_clean, sort_keys=True) == json.dumps(upstream_clean, sort_keys=True)


def update_pipeline_with_upstream(local_pipeline: Dict[str, Any], 
                                upstream_pipeline: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    """Update local pipeline with upstream values, preserving taskRef fields and specific parameters."""
    updated_pipeline = local_pipeline.copy()
    has_updates = False
    
    # Parameters to preserve from local pipeline (don't overwrite with upstream values)
    PRESERVE_PARAMS = {'hermetic', 'build-source-image', 'build-args', 'build-platforms'}
    
    # Get specs for comparison (without taskRef fields)
    local_spec = local_pipeline.get('spec', {})
    upstream_spec = upstream_pipeline.get('spec', {})
    
    # Compare specs
    specs_match = compare_specs(local_spec, upstream_spec)
    
    if not specs_match:
        print("=== DIFFERENCES FOUND ===")
        
        # Update top-level spec fields (except tasks, finally, and params which need special handling)
        for key, value in upstream_spec.items():
            if key not in ['tasks', 'finally', 'params']:
                if key not in local_spec or local_spec[key] != value:
                    print(f"Updating spec.{key}")
                    updated_pipeline['spec'][key] = value
                    has_updates = True
        
        # Handle params - preserve specific parameters while updating others
        if 'params' in upstream_spec:
            local_params = local_spec.get('params', [])
            upstream_params = upstream_spec['params']
            
            # Create lookup maps for easier processing
            local_params_map = {param.get('name'): param for param in local_params}
            upstream_params_map = {param.get('name'): param for param in upstream_params}
            
            # Build updated params list
            updated_params = []
            
            # First, add all upstream params, but preserve local values for specified params
            for upstream_param in upstream_params:
                param_name = upstream_param.get('name')
                
                if param_name in PRESERVE_PARAMS and param_name in local_params_map:
                    # Preserve local parameter
                    preserved_param = local_params_map[param_name].copy()
                    updated_params.append(preserved_param)
                    print(f"Preserving local value for param: {param_name}")
                else:
                    # Use upstream parameter
                    if param_name not in local_params_map or local_params_map[param_name] != upstream_param:
                        print(f"Updating param: {param_name}")
                        has_updates = True
                    updated_params.append(upstream_param)
            
            # Add any local params that don't exist in upstream (shouldn't happen normally)
            for local_param in local_params:
                param_name = local_param.get('name')
                if param_name not in upstream_params_map:
                    print(f"Keeping local-only param: {param_name}")
                    updated_params.append(local_param)
            
            updated_pipeline['spec']['params'] = updated_params
        
        # Handle tasks - preserve taskRef but update other fields
        if 'tasks' in upstream_spec:
            local_tasks = {task['name']: task for task in local_spec.get('tasks', [])}
            updated_tasks = []
            
            for upstream_task in upstream_spec['tasks']:
                task_name = upstream_task['name']
                if task_name in local_tasks:
                    # Update existing task, preserve taskRef
                    updated_task = upstream_task.copy()
                    if 'taskRef' in local_tasks[task_name]:
                        updated_task['taskRef'] = local_tasks[task_name]['taskRef']
                    updated_tasks.append(updated_task)
                else:
                    # New task from upstream
                    updated_tasks.append(upstream_task)
                    print(f"Adding new task: {task_name}")
                    has_updates = True
            
            updated_pipeline['spec']['tasks'] = updated_tasks
        
        # Handle finally tasks - preserve taskRef but update other fields
        if 'finally' in upstream_spec:
            local_finally = {task['name']: task for task in local_spec.get('finally', [])}
            updated_finally = []
            
            for upstream_task in upstream_spec['finally']:
                task_name = upstream_task['name']
                if task_name in local_finally:
                    # Update existing task, preserve taskRef
                    updated_task = upstream_task.copy()
                    if 'taskRef' in local_finally[task_name]:
                        updated_task['taskRef'] = local_finally[task_name]['taskRef']
                    updated_finally.append(updated_task)
                else:
                    # New task from upstream
                    updated_finally.append(upstream_task)
                    print(f"Adding new finally task: {task_name}")
                    has_updates = True
            
            updated_pipeline['spec']['finally'] = updated_finally
    
    return updated_pipeline, has_updates


def prompt_user_action(message: str, options: List[str]) -> str:
    """Prompt user for action choice."""
    print(f"\n{message}")
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")
    
    while True:
        try:
            choice = input("Choose an option (number): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            print("Invalid choice. Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            sys.exit(0)


def main():
    """Main function to orchestrate pipeline comparison and sync."""
    
    # Check if running in GitHub Action mode
    github_action_mode = os.environ.get('GITHUB_ACTION_MODE', 'false') == 'true'
    
    if github_action_mode:
        # Parse configuration from environment variables
        auto_patch = os.environ.get('AUTO_PATCH', 'false') == 'true'
        update_refs = os.environ.get('UPDATE_REFS', 'false') == 'true'
    else:
        # Parse command-line arguments
        auto_patch = "--auto-patch" in sys.argv
        update_refs = "--update-refs" in sys.argv
    
    print("=== Pipeline Sync Script ===")
    print(f"Processing {len(PIPELINE_MAPPINGS)} pipeline(s)")
    print()
    
    # Get script directory for downloading tools
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    overall_has_updates = False
    overall_missing_tasks = set()
    all_processed_pipelines = []
    
    for upstream_url, local_path in PIPELINE_MAPPINGS.items():
        print(f"📄 Processing pipeline: {local_path}")
        print(f"   Upstream: {upstream_url}")
        
        try:
            # Load pipelines
            print("   Fetching upstream pipeline...")
            upstream_pipeline = fetch_upstream_pipeline(upstream_url)
            
            print("   Loading local pipeline...")
            local_pipeline = load_local_pipeline(local_path)
            
            print("   Comparing pipelines...")
            
            # Extract task names
            local_tasks = get_task_names(local_pipeline.get('spec', {}))
            upstream_tasks = get_task_names(upstream_pipeline.get('spec', {}))
            
            # Find missing tasks
            missing_tasks = upstream_tasks - local_tasks
            extra_tasks = local_tasks - upstream_tasks
            
            print(f"   Local tasks: {len(local_tasks)} tasks")
            print(f"   Upstream tasks: {len(upstream_tasks)} tasks")
            
            if missing_tasks:
                print(f"   ⚠️  MISSING TASKS:")
                for task in sorted(missing_tasks):
                    print(f"     - {task}")
                overall_missing_tasks.update(missing_tasks)
            
            if extra_tasks:
                print(f"   🔍 EXTRA TASKS:")
                for task in sorted(extra_tasks):
                    print(f"     - {task}")
            
            # Update pipeline with upstream changes
            print(f"   === UPDATING PIPELINE ===")
            updated_pipeline, has_updates = update_pipeline_with_upstream(local_pipeline, upstream_pipeline)
            
            if has_updates:
                print("   ✅ Updates found - saving updated pipeline...")
                save_local_pipeline(local_path, updated_pipeline)
                print(f"   Pipeline updated successfully: {local_path}")
                overall_has_updates = True
            else:
                print("   ✅ No updates needed - local pipeline is up to date")
            
            # Store pipeline info for later processing
            all_processed_pipelines.append({
                'upstream_url': upstream_url,
                'local_path': local_path,
                'missing_tasks': missing_tasks,
                'has_updates': has_updates,
                'missing_tasks_patched': False  # Will be updated later if patching occurs
            })
            
        except Exception as e:
            print(f"   ❌ Error processing {local_path}: {e}")
            continue
        
        print()
    
    # Handle missing tasks with pipeline-patcher (for all pipelines)
    if overall_missing_tasks:
        print("=== MISSING TASK PATCHING ===")
        
        if auto_patch:
            patch_action = "Automatically patch missing tasks"
        else:
            patch_action = prompt_user_action(
                "What would you like to do about the missing tasks?",
                [
                    "Skip - just report missing tasks",
                    "Automatically patch missing tasks using konflux-pipeline-patcher",
                    "Update task bundle references to latest versions",
                    "Both - patch missing tasks and update bundle references"
                ]
            )
        
        if "patch" in patch_action.lower() or "both" in patch_action.lower():
            # Download pipeline-patcher tool
            patcher_path = download_pipeline_patcher(script_dir)
            
            if patcher_path:
                # Patch missing tasks for each pipeline
                for i, pipeline_info in enumerate(all_processed_pipelines):
                    if pipeline_info['missing_tasks']:
                        print(f"\n🔧 Patching missing tasks for {pipeline_info['local_path']}...")
                        patch_success = patch_missing_tasks(patcher_path, pipeline_info['local_path'], pipeline_info['missing_tasks'])
                        
                        if patch_success:
                            # Update the pipeline info to track patching success
                            all_processed_pipelines[i]['missing_tasks_patched'] = True
                            
                            print("🔄 Reloading pipeline after patching...")
                            local_pipeline = load_local_pipeline(pipeline_info['local_path'])
                            local_tasks = get_task_names(local_pipeline.get('spec', {}))
                            
                            # Re-fetch upstream to get current task names
                            upstream_pipeline = fetch_upstream_pipeline(pipeline_info['upstream_url'])
                            upstream_tasks = get_task_names(upstream_pipeline.get('spec', {}))
                            
                            remaining_missing = upstream_tasks - local_tasks
                            
                            if remaining_missing:
                                print(f"⚠️  Still missing tasks after patching:")
                                for task in sorted(remaining_missing):
                                    print(f"  - {task}")
                            else:
                                print("✅ All missing tasks have been patched!")
        
        if "update" in patch_action.lower() or "both" in patch_action.lower():
            if 'patcher_path' not in locals():
                patcher_path = download_pipeline_patcher(script_dir)
            
            if patcher_path:
                update_task_bundle_refs(patcher_path, '.')
    
    elif update_refs:
        print("=== UPDATING TASK BUNDLE REFERENCES ===")
        patcher_path = download_pipeline_patcher(script_dir)
        if patcher_path:
            update_task_bundle_refs(patcher_path, '.')
    
    print("=== SYNC COMPLETE ===")
    print(f"Processed {len(all_processed_pipelines)} pipeline(s)")
    print(f"Updates made: {overall_has_updates}")
    print(f"Missing tasks found: {len(overall_missing_tasks)}")
    
    # Set GitHub Action outputs if running in action mode
    if github_action_mode and 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"updated={str(overall_has_updates).lower()}\n")
            f.write(f"pipelines_processed={len(all_processed_pipelines)}\n")
            f.write(f"missing_tasks_found={str(bool(overall_missing_tasks)).lower()}\n")
            f.write(f"missing_tasks_patched={str(any(info.get('missing_tasks_patched', False) for info in all_processed_pipelines)).lower()}\n")
        
        # Generate changes summary
        all_changes = []
        for pipeline_info in all_processed_pipelines:
            if pipeline_info.get('has_updates', False):
                all_changes.append(f"- Updated {pipeline_info['local_path']} from upstream")
            if pipeline_info.get('missing_tasks_patched', False):
                missing_count = len(pipeline_info.get('missing_tasks', set()))
                all_changes.append(f"- Patched {missing_count} missing tasks in {pipeline_info['local_path']}")
            elif pipeline_info.get('missing_tasks', set()):
                missing_count = len(pipeline_info['missing_tasks'])
                all_changes.append(f"- Found {missing_count} missing tasks in {pipeline_info['local_path']} (auto-patch disabled)")
        
        changes_summary = "\n".join(all_changes) if all_changes else "No changes made"
        
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"changes_summary<<EOF\n{changes_summary}\nEOF\n")
    
    if not github_action_mode:
        print("\nUsage options:")
        print("  python3 scripts/sync-pipeline-configs.py                # Interactive mode")
        print("  python3 scripts/sync-pipeline-configs.py --auto-patch   # Auto-patch missing tasks")
        print("  python3 scripts/sync-pipeline-configs.py --update-refs  # Update task bundle references")


if __name__ == "__main__":
    main() 
