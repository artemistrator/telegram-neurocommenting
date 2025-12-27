import asyncio
import subprocess
import sys
import os

# Ensure we are in the project root
os.chdir(os.getcwd())

async def run_script(script_path: str):
    print(f"\n{'='*60}")
    print(f"RUNNING: {script_path}")
    print(f"{'='*60}")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    
    # Run the script and stream output
    process = await asyncio.create_subprocess_exec(
        sys.executable, script_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env
    )

    stdout, _ = await process.communicate()
    print(stdout.decode(errors='replace'))
    
    return process.returncode

async def main():
    print(">>> Universal Task Queue Validation Suite")
    
    scripts = [
        "backend/scripts/test_task_queue.py",
        "backend/scripts/stress_task_queue.py"
    ]
    
    results = []
    
    for script in scripts:
        if not os.path.exists(script):
            print(f"!!! Error: Script {script} not found.")
            results.append((script, 1))
            continue
            
        ret_code = await run_script(script)
        results.append((script, ret_code))
        
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    
    all_passed = True
    for script, code in results:
        status = "[PASS]" if code == 0 else "[FAIL]"
        if code != 0:
            all_passed = False
        print(f"{status} | {script}")
        
    if all_passed:
        print("\n*** ALL CHECKS PASSED SUCCESSFULLY! ***")
        sys.exit(0)
    else:
        print("\n!!! SOME CHECKS FAILED! !!!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
