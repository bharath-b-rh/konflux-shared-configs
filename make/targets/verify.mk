scripts_dir :=$(shell realpath $(dir $(lastword $(MAKEFILE_LIST)))../../hack)

## check shell scripts.
.PHONY: verify-shell-scripts
verify-shell-scripts:
	bash $(scripts_dir)/shell-scripts-linter.sh

## check containerfiles.
.PHONY: verify-containerfiles
verify-containerfiles:
	bash $(scripts_dir)/containerfile-linter.sh

## validate renovate config.
.PHONY: validate-renovate-config
validate-renovate-config:
	bash $(scripts_dir)/renovate-config-validator.sh

## verify the changes are working as expected.
.PHONY: verify
verify: verify-shell-scripts verify-containerfiles validate-renovate-config
