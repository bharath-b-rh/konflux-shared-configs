# Pipeline Sync Scripts

This directory contains scripts for synchronizing Tekton pipeline configurations with upstream [konflux-ci/build-definitions](https://github.com/konflux-ci/build-definitions) repository.

## sync-pipeline-configs.py

Enhanced script for intelligently syncing multiple Tekton pipeline configurations while preserving local customizations.

## Features

- ✅ **Multiple pipeline support** - Processes multiple pipeline mappings in a single run
- ✅ **Compares pipeline specs** - Identifies differences between local and upstream pipeline configurations
- ✅ **Preserves taskRef fields** - Maintains your local taskRef configurations (bundle URLs, SHAs) while updating other fields
- ✅ **Reports missing tasks** - Shows which tasks are missing from your local pipeline
- ✅ **Updates automatically** - Applies upstream changes to your local pipeline file
- ✅ **Auto-patches missing tasks** - Uses [konflux-pipeline-patcher](https://github.com/simonbaird/konflux-pipeline-patcher) to add missing tasks with proper taskRef configurations
- ✅ **Updates task bundle references** - Automatically updates task bundle references to latest versions
- ✅ **Interactive mode** - Prompts user for actions when missing tasks are found
- ✅ **Safe operation** - Creates a backup and only updates what's needed

## Requirements

```bash
pip install -r requirements.txt
```

Or manually install:
- `requests>=2.28.0` - For fetching upstream pipeline
- `PyYAML>=6.0` - For parsing YAML files

## Usage

### Configuration

The script uses a hardcoded `PIPELINE_MAPPINGS` dictionary to define which pipelines to sync:

```python
PIPELINE_MAPPINGS = {
    'https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/fbc-builder/fbc-builder.yaml': '.tekton/fbc-build-pipeline.yaml',
    # Add more mappings as needed
}
```

### Interactive Mode (Recommended)

```bash
python3 scripts/sync-pipeline-configs.py
```

When missing tasks are detected, the script will prompt you to choose an action:
1. Skip - just report missing tasks
2. Automatically patch missing tasks using konflux-pipeline-patcher
3. Update task bundle references to latest versions
4. Both - patch missing tasks and update bundle references

### Automated Modes

```bash
# Auto-patch missing tasks without prompting
python3 scripts/sync-pipeline-configs.py --auto-patch

# Update task bundle references to latest versions
python3 scripts/sync-pipeline-configs.py --update-refs
```

### Make it executable

```bash
chmod +x scripts/sync-pipeline-configs.py
./scripts/sync-pipeline-configs.py
```

## What the Script Does

1. **Fetches** the upstream pipeline from [`konflux-ci/build-definitions`](https://github.com/konflux-ci/build-definitions/blob/main/pipelines/fbc-builder/fbc-builder.yaml)
2. **Loads** your local pipeline from `.tekton/fbc-build-pipeline.yaml`
3. **Compares** the pipeline specs (excluding taskRef fields)
4. **Reports** any missing tasks in your local pipeline
5. **Updates** your local pipeline with upstream changes while preserving taskRef fields
6. **Downloads** [konflux-pipeline-patcher](https://github.com/simonbaird/konflux-pipeline-patcher) tool if missing tasks are found
7. **Patches** missing tasks automatically with proper taskRef configurations
8. **Updates** task bundle references to latest versions (optional)
9. **Saves** the updated pipeline back to `.tekton/fbc-build-pipeline.yaml`

## Example Output

```
=== Pipeline Sync Script ===
Processing 1 pipeline(s)

📄 Processing pipeline: .tekton/fbc-build-pipeline.yaml
   Upstream: https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/fbc-builder/fbc-builder.yaml
   Fetching upstream pipeline...
   Loading local pipeline...
   Comparing pipelines...
   Local tasks: 5 tasks
   Upstream tasks: 6 tasks
   ⚠️  MISSING TASKS:
     - clamav-scan
   === UPDATING PIPELINE ===
=== DIFFERENCES FOUND ===
Updating spec.description
Updating param: git-url
Updating param: revision
Preserving local value for param: hermetic
Preserving local value for param: build-platforms
   ✅ Updates found - saving updated pipeline...
   Pipeline updated successfully: .tekton/fbc-build-pipeline.yaml

=== MISSING TASK PATCHING ===

What would you like to do about the missing tasks?
1. Skip - just report missing tasks
2. Automatically patch missing tasks using konflux-pipeline-patcher
3. Update task bundle references to latest versions
4. Both - patch missing tasks and update bundle references
Choose an option (number): 2

📥 Downloading konflux-pipeline-patcher tool...
✅ Pipeline patcher downloaded to scripts/pipeline-patcher

🔧 Patching missing tasks for .tekton/fbc-build-pipeline.yaml...

🔧 Patching 1 missing tasks:
  - clamav-scan

✅ Successfully patched missing tasks

🔄 Reloading pipeline after patching...
✅ All missing tasks have been patched!

=== SYNC COMPLETE ===
Processed 1 pipeline(s)
Updates made: True
Missing tasks found: 1
```

## Key Features

### TaskRef Preservation
The script **preserves** your local `taskRef` configurations, which contain:
- Bundle URLs
- SHA256 digests
- Resolver configurations

This ensures your pipeline continues to use the specific task versions you've configured.

### Parameter Preservation
The script **preserves** specific local parameter values that you may have customized:
- `hermetic` - Build isolation settings
- `build-source-image` - Source image build configuration
- `build-args` - Custom build arguments
- `build-platforms` - Target build platforms

These parameters are not overwritten with upstream values, allowing you to maintain your project-specific configurations.

### Missing Task Detection & Auto-Patching
The script identifies tasks that exist in upstream but are missing from your local pipeline:
- Reports missing tasks by name
- Uses [konflux-pipeline-patcher](https://github.com/simonbaird/konflux-pipeline-patcher) to add missing tasks with proper taskRef configurations
- Automatically downloads and uses the pipeline-patcher tool
- Filters tasks to only patch those available in the pipeline-patcher database
- Maintains task order from upstream

### Bundle Reference Updates
- Updates task bundle references to latest trusted versions
- Uses the pipeline-patcher's trusted task database
- Preserves your pipeline structure while updating SHA digests

### Safe Updates
- Only updates fields that actually differ
- Preserves existing taskRef configurations
- Reports what changes are being made
- Interactive prompts for user confirmation

## Pipeline-Patcher Integration

The script automatically integrates with [Simon Baird's konflux-pipeline-patcher](https://github.com/simonbaird/konflux-pipeline-patcher) tool to:

### Automatic Tool Download
- Downloads the pipeline-patcher tool automatically when needed
- Stores it in the `scripts/` directory for reuse
- Makes it executable and ready to use

### Task Patching Capabilities
- **Add missing tasks**: Automatically adds tasks that exist in upstream but are missing locally
- **Proper taskRef generation**: Uses the pipeline-patcher's trusted task database to generate proper bundle references
- **Task availability checking**: Only patches tasks that are available in the pipeline-patcher database
- **Placement control**: Intelligently places new tasks in the correct location within the pipeline

### Bundle Reference Updates
- **Latest versions**: Updates task bundle references to the newest trusted versions
- **SHA digest updates**: Automatically updates SHA256 digests to latest
- **Batch updates**: Can update all task references in one operation

## Integration with CI/CD

You can integrate this script into your CI/CD pipeline:

### Basic Integration
```yaml
# .github/workflows/sync-pipeline.yml
- name: Sync Pipeline Configurations
  run: |
    python3 scripts/sync-pipeline-configs.py
    if [ -n "$(git status --porcelain .tekton/)" ]; then
      git add .tekton/
      git commit -m "NO-JIRA: Sync pipeline configurations with upstream"
    fi
```

### Auto-Patch Integration
```yaml
# .github/workflows/sync-pipeline.yml
- name: Sync Pipeline Configurations with Auto-Patch
  run: |
    python3 scripts/sync-pipeline-configs.py --auto-patch
    if [ -n "$(git status --porcelain .tekton/)" ]; then
      git add .tekton/fbc-build-pipeline.yaml
      git commit -m "NO-JIRA: Sync FBC pipeline with upstream and patch missing tasks"
    fi
```

### Bundle Reference Updates
```yaml
# .github/workflows/update-task-refs.yml
- name: Update Task Bundle References
  run: |
    python3 scripts/sync-fbc-pipeline.py --update-refs
    if [ -n "$(git status --porcelain .tekton/fbc-build-pipeline.yaml)" ]; then
      git add .tekton/fbc-build-pipeline.yaml
      git commit -m "NO-JIRA: Update task bundle references to latest versions"
    fi
```

## Configuration

The script uses these default paths:
- **Upstream**: `https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/fbc-builder/fbc-builder.yaml`
- **Local**: `.tekton/fbc-build-pipeline.yaml`

To customize these paths, edit the `UPSTREAM_URL` and `LOCAL_PIPELINE_PATH` variables in the script.

## Troubleshooting

### Network Issues
If you encounter network issues fetching the upstream pipeline:
```bash
# Test connectivity
curl -s https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/fbc-builder/fbc-builder.yaml
```

### Pipeline-Patcher Issues
If the pipeline-patcher tool fails to download or run:
```bash
# Check if the tool downloaded correctly
ls -la scripts/pipeline-patcher

# Test the tool directly
./scripts/pipeline-patcher help

# Manual download if needed
curl -sLO https://github.com/simonbaird/konflux-pipeline-patcher/raw/main/pipeline-patcher
chmod +x pipeline-patcher
```

### Pipeline-Patcher Dependencies
The pipeline-patcher tool requires these system dependencies:
- `bash`
- `curl`
- `awk`
- `sed`
- `jq`
- `git`
- `oras`
- `yq` (mikefarah version, not PyPI)

Install missing dependencies:
```bash
# On Ubuntu/Debian
sudo apt update
sudo apt install curl jq git

# Install yq (mikefarah version)
sudo wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
sudo chmod +x /usr/local/bin/yq

# Install oras
curl -LO https://github.com/oras-project/oras/releases/latest/download/oras_linux_amd64.tar.gz
tar -xzf oras_linux_amd64.tar.gz
sudo mv oras /usr/local/bin/
```

### YAML Parsing Errors
If you get YAML parsing errors:
```bash
# Validate your local YAML
python3 -c "import yaml; yaml.safe_load(open('.tekton/fbc-build-pipeline.yaml'))"
```

### Permission Errors
If you can't write to the local file:
```bash
# Check file permissions
ls -la .tekton/fbc-build-pipeline.yaml
chmod 644 .tekton/fbc-build-pipeline.yaml
``` 