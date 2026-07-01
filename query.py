import sys
import pandas as pd

def main():
    if len(sys.argv) < 2:
        print("Usage: python query.py \"<pandas code or expression>\"")
        print("Example: python query.py \"df[df['age'] > 30]['income'].value_counts()\"")
        return

    expr = sys.argv[1]
    csv_path = r"C:\Users\hi\ai_data-analyst-agent\census-income.csv.csv"
    
    try:
        df = pd.read_csv(csv_path, skipinitialspace=True)
        if df.columns[-1].startswith('Unnamed') or df.columns[-1].strip() == '':
            df.rename(columns={df.columns[-1]: 'income'}, inplace=True)
        df.columns = [col.strip() for col in df.columns]
        
        # Define a safe evaluation environment
        eval_env = {'df': df, 'pd': pd}
        
        # Execute code or evaluate expression
        if "=" in expr or ";" in expr or "print" in expr:
            # It's a statement
            exec(expr, eval_env)
        else:
            # It's an expression, evaluate and print
            result = eval(expr, eval_env)
            print("\n--- Result ---")
            print(result)
            
    except Exception as e:
        print(f"Error executing query: {e}")

if __name__ == "__main__":
    main()
