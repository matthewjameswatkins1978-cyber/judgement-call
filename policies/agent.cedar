// Cedar default deny policy permitting exact 6 product tools:
// list_tree, read_text, search_text, write_text, run_tests, request_decision

permit(
    principal,
    action in [
        Action::"list_tree",
        Action::"read_text",
        Action::"search_text",
        Action::"write_text",
        Action::"run_tests",
        Action::"request_decision"
    ],
    resource
);
