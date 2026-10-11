import sys
from pathlib import Path
sys.path.insert(0, ".")

from app.main import local_grounded_research

res = local_grounded_research("What is the procedure for obtaining a Kisan Credit Card (KCC) and what is the concessional interest rate?", language="en")
print("STATUS:", res["status"])
print("ANSWER:\n", res["final_answer"])
print("PRACTICAL STEPS:\n", res["practical_steps"])
