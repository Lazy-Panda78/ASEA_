import os
import subprocess
import sys

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running '{cmd}': {result.stderr}")
    return result

def main():
    if not os.path.exists('.git'):
        run_cmd('git init')
        run_cmd('git remote add origin https://github.com/Lazy-Panda78/ASEA_.git')
    
    # Get all untracked and modified files
    # We will use git ls-files --others --exclude-standard to get untracked
    status = run_cmd('git ls-files --others --exclude-standard')
    files = [f for f in status.stdout.split('\n') if f.strip()]
    
    # Also get modified files if any
    status_mod = run_cmd('git ls-files -m')
    files_mod = [f for f in status_mod.stdout.split('\n') if f.strip()]
    
    all_files = list(set(files + files_mod))
    
    print(f"Found {len(all_files)} files to commit individually.")
    
    for f in all_files:
        run_cmd(f'git add "{f}"')
        run_cmd(f'git commit -m "Add/Update {f}"')
        
    print("All files committed individually.")

if __name__ == "__main__":
    main()
