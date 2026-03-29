package github.fixtures

base_policy := {"policy": {
	"version": "1.0",
	"branch_rules": [
		{"source": "feature/*", "target": "develop"},
		{"source": "feature/*", "target": "main"},
		{"source": "bugfix/*", "target": "develop"},
		{"source": "hotfix/*", "target": "main"},
		{"source": "release/*", "target": "main"},
		{"source": "develop", "target": "main"},
	],
	"rules": {
		"allowed_target_branches": ["main", "develop"],
		"approvals_required": 1,
		"signed_off": false,
	},
}}

build_pr_input(head_ref, base_ref, approvers, signed_off, policy) := {
	"head_ref": head_ref,
	"base_ref": base_ref,
	"repo_policy": policy,
	"workflow_meta": {
		"approvers": approvers,
		"signed_off": signed_off,
	},
}
