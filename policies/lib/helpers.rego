package lib.helpers

import rego.v1

# =============================================================================
#  Shared helper functions used by all gitpoli policies.
# =============================================================================

# ── Type guards ───────────────────────────────────────────────────────────────

type_string(x) if {
	x != null
	type_name(x) == "string"
}

type_number(x) if {
	x != null
	type_name(x) == "number"
}

type_boolean(x) if {
	x != null
	type_name(x) == "boolean"
}

type_bool_strict(x) if x == true

type_bool_strict(x) if x == false

is_array_of_strings(arr) if {
	arr != null
	type_name(arr) == "array"
	not exists_non_string(arr)
}

exists_non_string(arr) if {
	some i
	i < count(arr)
	type_name(arr[i]) != "string"
}

# ── Safe casters ─────────────────────────────────────────────────────────────

safe_array(x) := x if {
	x != null
	type_name(x) == "array"
}

safe_array(x) := [] if x == null

safe_array(x) := [] if {
	x != null
	type_name(x) != "array"
}

string_or_empty(x) := x if {
	x != null
	type_name(x) == "string"
}

string_or_empty(x) := "" if x == null

string_or_empty(x) := "" if {
	x != null
	type_name(x) != "string"
}

number_or_zero(x) := x if {
	x != null
	type_name(x) == "number"
}

number_or_zero(x) := 0 if x == null

number_or_zero(x) := 0 if {
	x != null
	type_name(x) != "number"
}

bool_or_default(x, d) := x if {
	x != null
	type_name(x) == "boolean"
}

bool_or_default(x, d) := d if x == null

bool_or_default(x, d) := d if {
	x != null
	type_name(x) != "boolean"
}

# ── Truthiness ───────────────────────────────────────────────────────────────

truthy(x) if x == true

# ── Policy structure helpers ─────────────────────────────────────────────────

has_env_in_policy(inp) if {
	inp.repo_policy
	inp.repo_policy.policy
	inp.repo_policy.policy.version
	inp.repo_policy.policy.environments[inp.environment]
}

env_in_repo(env, repo_envs) if {
	some e in safe_array(repo_envs)
	e == env
}

branch_allowed(allowed, ref) if {
	some b in safe_array(allowed)
	ref == sprintf("refs/heads/%s", [b])
}

branch_allowed(allowed, ref) if {
	some b in safe_array(allowed)
	glob.match(sprintf("refs/heads/%s", [b]), ["/"], ref)
}

# ── Branch naming convention ─────────────────────────────────────────────────

# Strip refs/heads/ prefix from a ref, return the branch name.
strip_refs_prefix(ref) := name if {
	startswith(ref, "refs/heads/")
	name := substring(ref, count("refs/heads/"), -1)
}

strip_refs_prefix(ref) := ref if {
	not startswith(ref, "refs/heads/")
}

# Check if a branch name matches a glob pattern (e.g. "feature/*" matches "feature/login").
branch_name_matches(pattern, branch) if {
	glob.match(pattern, ["/"], branch)
}

# Check if a (source, target) pair matches any rule in the branch_rules list.
branch_rule_matches(branch_rules, source_branch, target_branch) if {
	some rule in safe_array(branch_rules)
	branch_name_matches(rule.source, source_branch)
	branch_name_matches(rule.target, target_branch)
}
