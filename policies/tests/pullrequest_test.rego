package github.pullrequest_test

import rego.v1

import data.github.fixtures as fixtures
import data.github.pullrequest as pr

# =============================================================================
#  Tests for the pull request policy (github.pullrequest)
# =============================================================================

# ── Basic rules tests ────────────────────────────────────────────────────────

test_allow_valid_pr if {
	test_input := fixtures.build_pr_input("feature/login", "develop", ["erasmo"], false, fixtures.base_policy)
	pr.allow with input as test_input
}

test_deny_target_branch_not_allowed if {
	test_input := fixtures.build_pr_input(
		"feature/abc",
		"staging",
		["erasmo"],
		false,
		fixtures.base_policy,
	)
	not pr.allow with input as test_input
	vs := pr.target_branch_violations with input as test_input
	count(vs) == 1
}

test_deny_missing_approvers if {
	test_input := {
		"head_ref": "feature/login",
		"base_ref": "develop",
		"repo_policy": base_policy,
		"workflow_meta": {
			"approvers": [],
			"signed_off": false,
		},
	}
	not pr.allow with input as test_input
	vs := pr.approval_violations with input as test_input
	count(vs) == 1
}

test_deny_missing_policy_rules if {
	test_input := {
		"head_ref": "feature/login",
		"base_ref": "develop",
		"repo_policy": {"policy": {"version": "1.0"}},
		"workflow_meta": {
			"approvers": ["erasmo"],
			"signed_off": false,
		},
	}
	not pr.allow with input as test_input
	vs := pr.policy_missing_violations with input as test_input
	count(vs) == 1
}

# ── Branch naming convention tests ───────────────────────────────────────────

test_branch_naming_feature_to_develop_allowed if {
	test_input := {
		"head_ref": "feature/login",
		"base_ref": "develop",
		"repo_policy": base_policy,
		"workflow_meta": {
			"approvers": ["erasmo"],
			"signed_off": false,
		},
	}
	pr.allow with input as test_input
}

test_branch_naming_feature_to_production_denied if {
	test_input := {
		"head_ref": "feature/login",
		"base_ref": "production",
		"repo_policy": base_policy,
		"workflow_meta": {
			"approvers": ["erasmo"],
			"signed_off": false,
		},
	}
	not pr.allow with input as test_input
	vs := pr.branch_naming_violations with input as test_input
	count(vs) == 1
}

test_branch_naming_hotfix_to_main_allowed if {
	test_input := {
		"head_ref": "hotfix/critical-bug",
		"base_ref": "main",
		"repo_policy": base_policy,
		"workflow_meta": {
			"approvers": ["erasmo"],
			"signed_off": false,
		},
	}
	pr.allow with input as test_input
}

test_branch_naming_skipped_when_no_rules if {
	policy_no_rules := {"policy": {
		"version": "1.0",
		"rules": {
			"allowed_target_branches": null,
			"approvals_required": 0,
			"signed_off": false,
		},
	}}
	test_input := {
		"head_ref": "random/branch",
		"base_ref": "whatever",
		"repo_policy": policy_no_rules,
		"workflow_meta": {
			"approvers": [],
			"signed_off": false,
		},
	}
	pr.allow with input as test_input
}

# ── Sign-off tests ───────────────────────────────────────────────────────────

test_deny_missing_signoff if {
	policy_signoff := {"policy": {
		"version": "1.0",
		"rules": {
			"allowed_target_branches": ["main"],
			"approvals_required": 0,
			"signed_off": true,
		},
	}}
	test_input := {
		"head_ref": "develop",
		"base_ref": "main",
		"repo_policy": policy_signoff,
		"workflow_meta": {
			"approvers": [],
			"signed_off": false,
		},
	}
	not pr.allow with input as test_input
	vs := pr.signoff_violations with input as test_input
	count(vs) == 1
}
