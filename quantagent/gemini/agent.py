import os
import json
import pandas as pd
import torch

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# Set your Gemini API Key
os.environ["GOOGLE_API_KEY"] = "AIzaSyASH8-1_nlejJYcogGt0BiL55f0a_Esh2o"

# Initialize Gemini 1.5 Flash
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)

# ==========================================
# CHILD AGENT TOOLS (Data & File Access Only)
# ==========================================

@tool
def analyze_price_history(product: str, day: int) -> str:
    """Reads the prices CSV for a specific day and product from the dataset folder. 
    Returns the average mid_price, order book imbalance, and volatility."""
    file_path = os.path.join("dataset", f"prices_round_0_day_{day}.csv")
    try:
        if not os.path.exists(file_path):
            return f"Error: File {file_path} not found."
            
        df = pd.read_csv(file_path, sep=';')
        
        product_df = df[df['product'] == product]
        if product_df.empty:
            return f"No data found for product {product} on day {day}."
            
        avg_mid_price = product_df['mid_price'].mean()
        volatility = product_df['mid_price'].std()
        
        avg_bid_vol = product_df['bid_volume_1'].mean()
        avg_ask_vol = product_df['ask_volume_1'].mean()
        
        return (f"Price Analysis for {product} on Day {day}:\n"
                f"- Avg Mid Price: {avg_mid_price:.2f}\n"
                f"- Volatility (Std Dev): {volatility:.2f}\n"
                f"- Avg Bid Volume 1: {avg_bid_vol:.2f}\n"
                f"- Avg Ask Volume 1: {avg_ask_vol:.2f}")
    except Exception as e:
        return f"Error analyzing prices: {str(e)}"

@tool
def list_available_runs() -> str:
    """Scans the logs/ directory and returns a list of all numeric run IDs available."""
    try:
        if not os.path.exists("logs"):
            return "Error: 'logs' directory not found."
            
        run_ids = [d for d in os.listdir("logs") 
                   if d.isdigit() and os.path.isdir(os.path.join("logs", d))]
                   
        if not run_ids:
            return "No numeric run ID folders found in the logs directory."
            
        return f"Available simulation run IDs: {', '.join(run_ids)}"
    except Exception as e:
        return f"Error listing runs: {str(e)}"

@tool
def parse_simulation_logs(run_id: str) -> str:
    """Parses a Prosperity .json log file for a specific run_id to extract PnL and print statements."""
    log_file = os.path.join("logs", str(run_id), f"{run_id}.json")
    try:
        if not os.path.exists(log_file):
            return f"Error: Log file {log_file} not found."
            
        with open(log_file, 'r') as f:
            data = f.read()
            try:
                log_data = json.loads(data)
            except json.JSONDecodeError:
                return "Error: Log file is not valid JSON."

        result_str = f"--- Analysis of Run {run_id} ---\n"
        if 'profit' in log_data:
            result_str += f"Final Total Profit: {log_data['profit']}\n"
            
        if 'sandboxLogs' in log_data:
            sandbox_logs = log_data['sandboxLogs']
            sample_prints = "\n".join([str(log.get('print', '')) for log in sandbox_logs[-5:] if 'print' in log])
            result_str += f"Recent Sandbox Print Outputs:\n{sample_prints}\n"
            
        return result_str
    except Exception as e:
        return f"Error parsing logs: {str(e)}"

@tool
def read_strategy_code(run_id: str) -> str:
    """Reads the Python source code of the Trader class submitted for a specific run_id."""
    py_file = os.path.join("logs", str(run_id), f"{run_id}.py")
    try:
        if not os.path.exists(py_file):
            return f"Error: Strategy file {py_file} not found."
            
        with open(py_file, 'r') as f:
            code = f.read()
            
        return f"Source code for Run {run_id}:\n\n```python\n{code}\n```"
    except Exception as e:
        return f"Error reading python file: {str(e)}"

@tool
def load_and_evaluate_dl_model(model_path: str) -> str:
    """Loads an offline-trained PyTorch model (.pt or .pth) used for predicting price movements."""
    try:
        if not os.path.exists(model_path):
            return f"Model file {model_path} not found. Skipping evaluation."
            
        model = torch.load(model_path, weights_only=False)
        return f"Successfully loaded PyTorch model from {model_path}."
    except Exception as e:
        return f"Error loading PyTorch model: {str(e)}"

# ==========================================
# CHILD AGENT DEFINITION
# ==========================================

child_tools = [
    analyze_price_history,
    list_available_runs,
    parse_simulation_logs,
    read_strategy_code,
    load_and_evaluate_dl_model
]

child_system_prompt = (
    "You are the Data Analyst Sub-Agent. Your sole responsibility is to use your "
    "available tools to scan directories, read CSV datasets, parse logs, and read python code. "
    "Once you have gathered the requested data, output a highly detailed, numerical, "
    "and structural summary of what you found so the Main Agent can formulate a strategy."
)

child_agent = create_react_agent(llm, tools=child_tools, prompt=child_system_prompt)

# ==========================================
# MAIN AGENT DELEGATION TOOL
# ==========================================

@tool
def delegate_to_data_analyst(task_instructions: str) -> str:
    """Delegates data fetching, file reading, and log parsing to the Data Analyst Sub-Agent.
    Pass explicit instructions on what datasets or run IDs to investigate."""
    print(f"\n[Main Agent] Delegating to Child Agent: {task_instructions}")
    
    inputs = {"messages": [HumanMessage(content=task_instructions)]}
    response = child_agent.invoke(inputs)
    
    summary = response["messages"][-1].content
    print(f"\n[Child Agent] Summary returned to Main Agent:\n{summary}\n")
    return summary

# ==========================================
# MAIN AGENT DEFINITION
# ==========================================

main_tools = [delegate_to_data_analyst]

main_system_prompt = (
    "You are the Lead Quant Strategist. You do NOT have direct access to files or datasets. "
    "You must rely entirely on your 'delegate_to_data_analyst' tool to fetch data summaries, "
    "read python code, and parse log files. "
    "First, delegate tasks to the Data Analyst. "
    "Second, wait for their detailed summary. "
    "Finally, provide your authoritative strategic analysis and code improvement suggestions "
    "to the user."
)

main_agent = create_react_agent(llm, tools=main_tools, prompt=main_system_prompt)

# ==========================================
# EXECUTION ROUTINE
# ==========================================

if __name__ == "__main__":
    print("🚀 Initializing Multi-Agent Quant System...\n")
    
    user_prompt = (
        "Check which runs are available in the logs directory. "
        "For run 58907, read the strategy code and the simulation logs. "
        "Also, pull the price history for TOMATOES on day -1 from the dataset. "
        "Combine this information to tell me why my strategy is performing this way."
    )
    
    inputs = {"messages": [HumanMessage(content=user_prompt)]}
    
    # Invoking the main agent handles the full execution flow, 
    # pausing to query the child agent before returning the final response.
    final_response = main_agent.invoke(inputs)
    
    print("==========================================")
    print("🤖 Final Strategist Analysis:")
    print("==========================================")
    print(final_response["messages"][-1].content)