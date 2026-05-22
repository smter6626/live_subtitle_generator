from stream_transcribe import simple_dedup, fuzzy_boundary_dedup


def run_case(case):
    name = case["name"]
    old_text = case["old_text"]
    new_text = case["new_text"]
    expect_s1 = case.get("expect_stage1_changed")
    expect_s2 = case.get("expect_stage2_changed")
    expect_substring = case.get("expect_final_contains")
    reject_substring = case.get("reject_final_contains")

    print(f"\n=== {name} ===")
    stage1 = simple_dedup(new_text, old_text)
    stage2 = fuzzy_boundary_dedup(old_text, stage1)

    s1_changed = stage1 != new_text
    s2_changed = stage2 != stage1

    print("OLD:")
    print(old_text)
    print("NEW:")
    print(new_text)
    print("STAGE1:")
    print(repr(stage1))
    print("STAGE2:")
    print(repr(stage2))
    print("S1 changed:", s1_changed)
    print("S2 changed:", s2_changed)

    checks = []

    if expect_s1 is not None:
        checks.append(("expect_stage1_changed", s1_changed == expect_s1))

    if expect_s2 is not None:
        checks.append(("expect_stage2_changed", s2_changed == expect_s2))

    if expect_substring is not None:
        checks.append(("expect_final_contains", expect_substring in stage2))

    if reject_substring is not None:
        checks.append(("reject_final_contains", reject_substring not in stage2))

    all_pass = all(ok for _, ok in checks) if checks else True

    for label, ok in checks:
        print(f"{label}: {'PASS' if ok else 'FAIL'}")

    print("CASE RESULT:", "PASS" if all_pass else "FAIL")

    return {
        "name": name,
        "stage1": stage1,
        "stage2": stage2,
        "s1_changed": s1_changed,
        "s2_changed": s2_changed,
        "passed": all_pass,
    }


def main():
    cases = [
        # 1. 精确重叠：Stage 1 应该直接处理
        {
            "name": "Exact overlap - baseline",
            "old_text": "[0.00s -> 4.00s] today we discuss bayesian networks and inference",
            "new_text": "[7.00s -> 11.00s] bayesian networks and inference in more detail",
            "expect_stage1_changed": True,
            "expect_stage2_changed": False,
            "expect_final_contains": "[7.00s -> 11.00s]",
        },

        # 2. contraction：当前 compare layer 应让 Stage 1 直接吃掉
        {
            "name": "Contraction handled by Stage 1",
            "old_text": "[0.00s -> 4.00s] we will now discuss the first example",
            "new_text": "[7.00s -> 11.00s] we'll now discuss the first example in class",
            "expect_stage1_changed": True,
            "expect_stage2_changed": False,
            "expect_final_contains": "in class",
        },

        # 3. lexical variation：期望 Stage 2 介入
        {
            "name": "Fuzzy lexical variation - basic/core",
            "old_text": "[0.00s -> 4.00s] today we discuss the basic idea of probabilistic graphical models",
            "new_text": "[7.00s -> 11.00s] today we discuss the core idea of probabilistic graphical models in class",
            "expect_stage1_changed": False,
            "expect_stage2_changed": True,
            "expect_final_contains": "in class",
            "reject_final_contains": "today we discuss the core idea",
        },

        # 4. lexical variation：关系词替换
        {
            "name": "Fuzzy lexical variation - relationship/connection",
            "old_text": "[0.00s -> 4.00s] this example shows the relationship between the variables very clearly",
            "new_text": "[7.00s -> 11.00s] this example shows the connection between the variables very clearly here",
            "expect_stage1_changed": False,
            "expect_stage2_changed": True,
            "expect_final_contains": "here",
            "reject_final_contains": "this example shows the connection",
        },

        # 5. 近似但还不够：debug near miss 可接受，不要求 Stage 2 命中
        {
            "name": "Near miss - compute/calculate",
            "old_text": "[0.00s -> 4.00s] we can compute the value by using dynamic programming",
            "new_text": "[7.00s -> 11.00s] we can calculate the value by using dynamic programming step by step",
            "expect_stage1_changed": False,
            "expect_stage2_changed": False,
            "expect_final_contains": "we can calculate the value",
        },

        # 6. filler 变化但实质重复：看 Stage 2 是否能适度处理
        {
            "name": "Fuzzy with filler insertion",
            "old_text": "[0.00s -> 4.00s] today we discuss markov decision processes",
            "new_text": "[7.00s -> 11.00s] okay today we discuss markov decision processes in class",
            "expect_stage1_changed": False,
            "expect_final_contains": "[7.00s -> 11.00s]",
        },

        # 7. 套话相似但含义不同：绝不能误删
        {
            "name": "Negative - same frame different meaning",
            "old_text": "[0.00s -> 4.00s] in this example we analyze the training procedure for the first model",
            "new_text": "[7.00s -> 11.00s] in this example we analyze the convergence behavior of the second model",
            "expect_stage1_changed": False,
            "expect_stage2_changed": False,
            "expect_final_contains": "convergence behavior",
        },

        # 8. 实体不同：绝不能误删
        {
            "name": "Negative - entity changed",
            "old_text": "[0.00s -> 4.00s] today we discuss support vector machines in detail",
            "new_text": "[7.00s -> 11.00s] today we discuss bayesian networks in detail",
            "expect_stage1_changed": False,
            "expect_stage2_changed": False,
            "expect_final_contains": "bayesian networks",
        },

        # 9. 第一行内部裁剪：必须保留 timestamp
        {
            "name": "Timestamp preserve - trim inside first line",
            "old_text": "[0.00s -> 4.00s] bayesian networks are useful for representing uncertainty",
            "new_text": "[7.00s -> 11.00s] networks are useful for representing uncertainty in many tasks\n"
                        "[11.00s -> 14.00s] and now we discuss inference",
            "expect_stage1_changed": True,
            "expect_stage2_changed": False,
            "expect_final_contains": "[7.00s -> 11.00s]",
        },

        # 10. 第一行整行删除后跳到第二行：必须保留第二行 timestamp
        {
            "name": "Timestamp preserve - whole first line removed",
            "old_text": "[0.00s -> 2.00s] this is the first point\n"
                        "[2.00s -> 4.00s] this is the second point",
            "new_text": "[7.00s -> 9.00s] this is the second point\n"
                        "[9.00s -> 11.00s] this is the third point",
            "expect_stage1_changed": True,
            "expect_stage2_changed": False,
            "expect_final_contains": "[9.00s -> 11.00s] this is the third point",
        },

        # 11. 多行 fuzzy：第二行开头 overlap
        {
            "name": "Multiline fuzzy overlap - second line start",
            "old_text": "[0.00s -> 2.00s] today we start with the first definition\n"
                        "[2.00s -> 4.00s] conditional independence is very important in this model",
            "new_text": "[7.00s -> 9.00s] conditional independence is extremely important in this model for inference\n"
                        "[9.00s -> 11.00s] then we move to the next example",
            "expect_stage1_changed": False,
            "expect_stage2_changed": True,
            "expect_final_contains": "for inference",
        },

        # 12. 多行负例：实体变化，不能删
        {
            "name": "Multiline negative - entity changed",
            "old_text": "[0.00s -> 2.00s] today we review support vector machines\n"
                        "[2.00s -> 4.00s] the margin is the key concept",
            "new_text": "[7.00s -> 9.00s] today we review bayesian networks\n"
                        "[9.00s -> 11.00s] the graph structure is the key concept",
            "expect_stage1_changed": False,
            "expect_stage2_changed": False,
            "expect_final_contains": "bayesian networks",
        },

        # 13. cross-line near miss：当前可接受为不命中，但最好有 debug
        {
            "name": "Cross-line near miss",
            "old_text": "[0.00s -> 2.00s] we now turn to the next topic\n"
                        "[2.00s -> 4.00s] the first assumption is that the variables are independent",
            "new_text": "[7.00s -> 9.00s] the first assumption is that the variables are mostly independent\n"
                        "[9.00s -> 11.00s] this is not always true in practice",
            "expect_stage1_changed": False,
            "expect_stage2_changed": False,
            "expect_final_contains": "mostly independent",
        },

        # 14. 完全重复：应删空
        {
            "name": "Full overlap",
            "old_text": "[0.00s -> 4.00s] this is exactly the same sentence",
            "new_text": "[7.00s -> 11.00s] this is exactly the same sentence",
            "expect_stage1_changed": True,
            "expect_stage2_changed": False,
            "expect_final_contains": "",
        },
    ]

    results = []
    for case in cases:
        results.append(run_case(case))

    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    print("\n=== Final Summary ===")
    print(f"Passed {passed}/{total} cases")

    for r in results:
        print(
            f"{r['name']}: "
            f"{'PASS' if r['passed'] else 'FAIL'} | "
            f"S1_changed={r['s1_changed']} "
            f"S2_changed={r['s2_changed']} "
            f"Final={repr(r['stage2'])}"
        )


if __name__ == "__main__":
    main()