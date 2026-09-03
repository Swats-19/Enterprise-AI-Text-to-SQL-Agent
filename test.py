from skills.orchestrator import run_agent


print("\n========== FIRST RUN ==========")

result = run_agent(
    "Show me the top 5 products by sales",
    demo_mode=True,
    skip_human=False
)

print("\nFIRST RESULT:")
print(result)


if result.get("status") != "needs_human_approval":
    print("\n❌ Did not reach human approval.")
    raise SystemExit(1)


thread_id = result["thread_id"]

print("\n========== RESUMING SAME THREAD ==========")
print(f"Thread ID: {thread_id}")


result = run_agent(
    "",
    resume=True,
    human_decision={
        "approved": True
    },
    thread_id=thread_id
)

print("\nRESUMED RESULT:")
print(result)


print("\n========== TEST COMPLETE ==========")