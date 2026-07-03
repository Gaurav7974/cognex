import sys
from pathlib import Path
eval_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(eval_dir))
src_dir = eval_dir.parent / 'src'
sys.path.insert(0, str(src_dir))
from run_eval import main
if __name__ == '__main__':
    main()