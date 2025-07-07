# Sync Konflux Pipeline Configurations Action

This reusable GitHub Action intelligently synchronizes local Tekton pipeline configurations with upstream Konflux build-definitions while preserving your customizations.

## Features

- 🔄 **Smart pipeline syncing** - Updates from upstream while preserving local customizations
- 📄 **Multiple pipeline support** - Configurable pipeline mappings for different project needs
- 🔒 **TaskRef preservation** - Maintains your bundle URLs and SHA digests  
- ⚙️ **Parameter preservation** - Keeps your custom hermetic, build-source-image, build-args, build-platforms values
- 🔧 **Auto-patch missing tasks** - Uses konflux-pipeline-patcher to add missing tasks with proper taskRef configurations
- 📦 **Bundle reference updates** - Optionally updates task bundle references to latest versions
- 📝 **Detailed PR summaries** - Creates pull requests with comprehensive change descriptions
- 🏷️ **Configurable labels** - Customizable commit message prefixes and PR labels

## Usage

### Basic Usage

```yaml
name: Sync Konflux Pipeline Configurations

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM UTC
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Sync pipeline configurations with auto-patch
        uses: openshift/external-secrets-operator-release/.github/actions/sync-konflux-pipelines@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_patch_missing_tasks: 'true'
```

### Advanced Usage with Bundle Updates

```yaml
- name: Sync pipeline configurations and update bundle references
  uses: openshift/external-secrets-operator-release/.github/actions/sync-konflux-pipelines@main
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    auto_patch_missing_tasks: 'true'
    update_task_bundle_refs: 'true'
    commit_message_prefix: "PROJ-123: "
    pr_labels: "dependencies,konflux-sync,automation"
```

### Conservative Mode (No Auto-Patching)

```yaml
- name: Sync pipeline configurations without auto-patching
  uses: openshift/external-secrets-operator-release/.github/actions/sync-konflux-pipelines@main
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    auto_patch_missing_tasks: 'false'
    update_task_bundle_refs: 'false'
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `auto_patch_missing_tasks` | Automatically patch missing tasks using konflux-pipeline-patcher | No | `true` |
| `update_task_bundle_refs` | Update task bundle references to latest versions | No | `false` |
| `github_token` | GitHub token for creating PRs | Yes | - |
| `commit_message_prefix` | Prefix for commit messages | No | `NO-JIRA: ` |
| `pr_labels` | Comma-separated list of labels for PRs | No | `dependencies,pipeline-sync,automated-pr` |

## Outputs

| Output | Description |
|--------|-------------|
| `updated` | Whether any pipelines were updated (`true`/`false`) |
| `pipelines_processed` | Number of pipelines processed |
| `missing_tasks_found` | Whether missing tasks were found (`true`/`false`) |
| `missing_tasks_patched` | Whether missing tasks were successfully patched (`true`/`false`) |
| `pr_number` | PR number if a pull request was created |

## Pipeline Mappings

The pipeline mappings are configured directly in the `scripts/sync-pipeline-configs.py` file. To customize for your repository, edit the `PIPELINE_MAPPINGS` dictionary in that script:

```python
PIPELINE_MAPPINGS = {
    'https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/fbc-builder/fbc-builder.yaml': '.tekton/fbc-build-pipeline.yaml',
    'https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/docker-build/docker-build.yaml': '.tekton/docker-build-pipeline.yaml',
    # Add more mappings as needed
}
```

## How It Works

The action performs intelligent pipeline synchronization for multiple pipelines:

1. **Iterates** through all configured pipeline mappings
2. **Fetches** each upstream pipeline from konflux-ci/build-definitions
3. **Compares** with your local pipeline, excluding taskRef fields and preserved parameters
4. **Updates** your pipeline with upstream changes while preserving:
   - TaskRef configurations (bundle URLs, SHA digests)
   - Custom parameter values (hermetic, build-source-image, build-args, build-platforms)
5. **Auto-patches** missing tasks using the konflux-pipeline-patcher tool (if enabled)
6. **Updates** task bundle references to latest versions (if enabled)
7. **Creates** a pull request with detailed change summary for all processed pipelines

## Preserved Customizations

The action **automatically preserves** these local customizations:
- **TaskRef fields**: Your bundle URLs and SHA256 digests remain untouched
- **Parameter values**: `hermetic`, `build-source-image`, `build-args`, `build-platforms`
- **Local-only parameters**: Any parameters unique to your pipeline

## Repository Setup

### 1. Create Workflow File

Create `.github/workflows/sync-pipeline-configs.yml` in your repository:

```yaml
name: Sync Konflux Pipeline Configurations

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM UTC
  workflow_dispatch:

jobs:
  sync-pipelines:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Sync pipeline configurations
        uses: openshift/external-secrets-operator-release/.github/actions/sync-konflux-pipelines@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_patch_missing_tasks: 'true'
          update_task_bundle_refs: 'false'
```

### 2. Configure Repository Permissions

Ensure your repository has the following permissions enabled:
- **Settings → Actions → General → Workflow permissions**: "Read and write permissions"
- **Settings → Actions → General → Allow GitHub Actions to create and approve pull requests**: Enabled

### 3. Customize for Your Project

Update the `PIPELINE_MAPPINGS` dictionary in the standalone script to match your project's pipeline structure and requirements. Edit `scripts/sync-pipeline-configs.py` and modify the configuration section:

```python
PIPELINE_MAPPINGS = {
    'https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/fbc-builder/fbc-builder.yaml': '.tekton/fbc-build-pipeline.yaml',
    'https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/docker-build/docker-build.yaml': '.tekton/docker-build-pipeline.yaml',
    # Add your specific pipeline mappings here
}
```

## Reusability

This action is designed to be reusable across different OpenShift repositories that use Konflux pipelines. To use it in other projects:

1. **Copy the action**: Copy the entire `.github/actions/sync-konflux-pipelines` directory and `scripts/sync-pipeline-configs.py` file to your repository
2. **Customize mappings**: Update the `PIPELINE_MAPPINGS` dictionary in `scripts/sync-pipeline-configs.py` to match your repository's pipeline locations
3. **Configure schedule**: Adjust the cron schedule to fit your maintenance schedule
4. **Set permissions**: Ensure the workflow has `contents: write` and `pull-requests: write` permissions

### Example for Different Repository Structure

```yaml
with:
  github_token: ${{ secrets.GITHUB_TOKEN }}
  auto_patch_missing_tasks: 'true'
  update_task_bundle_refs: 'false'
  commit_message_prefix: "INFRA-"
  pr_labels: "infrastructure,automation"
```

Then customize the `PIPELINE_MAPPINGS` in the `scripts/sync-pipeline-configs.py` file:

```python
PIPELINE_MAPPINGS = {
    'https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/fbc-builder/fbc-builder.yaml': 'ci/tekton/fbc-pipeline.yaml',
    'https://raw.githubusercontent.com/konflux-ci/build-definitions/main/pipelines/docker-build/docker-build.yaml': 'ci/tekton/docker-pipeline.yaml',
}
```

### Multi-Pipeline Processing

The action automatically processes all pipelines defined in the `PIPELINE_MAPPINGS` dictionary in a single workflow run. This is more efficient than separate jobs and provides a consolidated PR with all changes.

## Troubleshooting

### Dependencies

The action automatically installs required Python dependencies:
- `requests` - for fetching upstream pipeline
- `PyYAML` - for YAML parsing and manipulation

### Pipeline Patcher

The action automatically downloads the `konflux-pipeline-patcher` tool when needed. If you encounter issues:
1. Check the action logs for download errors
2. Verify the tool is available at: https://github.com/simonbaird/konflux-pipeline-patcher
3. Set `auto_patch_missing_tasks: 'false'` if you prefer manual task management

### Pipeline Mappings

To add or modify pipeline mappings, edit the `PIPELINE_MAPPINGS` dictionary in the `scripts/sync-pipeline-configs.py` file. Each entry maps an upstream pipeline URL to a local file path.

## Example Repositories

- [external-secrets-operator-release](https://github.com/openshift/external-secrets-operator-release) - Reference implementation with FBC pipeline
- Add your repository here!

## Contributing

This action is maintained as part of the external-secrets-operator-release project. For issues or improvements, please open an issue in the [main repository](https://github.com/openshift/external-secrets-operator-release/issues). 