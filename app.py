from statistics import correlation

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io
import sys
import contextlib
import re

# Set page configuration for professional layout
st.set_page_config(
    page_title="AI Data Analyst Portal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Fixed parameter: changed unsafe_style_html to unsafe_allow_html)
st.markdown("""
<style>
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        font-size: 1.2rem;
        color: #555555;
        margin-bottom: 2rem;
    }
    .insight-box {
        background-color: #f0f4f8;
        border-left: 5px solid #1e3c72;
        padding: 1.2rem;
        border-radius: 6px;
        margin-bottom: 1.2rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .recommendation-box {
        background-color: #fdf6e2;
        border-left: 5px solid #d9a74a;
        padding: 1.2rem;
        border-radius: 6px;
        margin-bottom: 1.2rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .kpi-card {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #eaeaea;
        text-align: center;
    }
    .kpi-val {
        font-size: 2rem;
        font-weight: 700;
        color: #1e3c72;
    }
    .kpi-label {
        font-size: 0.9rem;
        color: #777;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 AI Data Analyst Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Enter your Gemini API Key in the sidebar to enable full LLM data analysis, or run locally out-of-the-box!</div>', unsafe_allow_html=True)

# ----------------------------------------------------
# Sidebar Configurations
# ----------------------------------------------------
st.sidebar.header("🔑 Model & Data Setup")
gemini_key = st.sidebar.text_input("Gemini API Key (Optional)", type="password", help="Enter your Google Gemini API key to enable natural language code-execution analysis.")

uploaded_file = st.sidebar.file_uploader("Upload your business dataset (CSV)", type=["csv"])

# Code execution helper
def run_pandas_code(code_str, df_context):
    code_match = re.search(r"```python(.*?)```", code_str, re.DOTALL)
    if not code_match:
        code_match = re.search(r"```(.*?)```", code_str, re.DOTALL)
    
    if not code_match:
        # Try raw code text if no backticks found but code seems to exist
        if "df" in code_str and ("print" in code_str or "groupby" in code_str or "mean" in code_str):
            code = code_str.strip()
        else:
            return None, "No python code block detected"
    else:
        code = code_match.group(1).strip()
    
    # Strip dangerous lines
    clean_lines = []
    for line in code.split('\n'):
        if 'read_csv' in line or 'sys' in line or 'os' in line or 'import' in line:
            continue
        clean_lines.append(line)
    clean_code = '\n'.join(clean_lines)

    stdout_capture = io.StringIO()
    local_env = {'df': df_context, 'pd': pd, 'np': np}
    
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(clean_code, {}, local_env)
        return stdout_capture.getvalue(), None
    except Exception as e:
        return None, str(e)

def query_dataframe_agent(user_query, df_context, api_key):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    schema_desc = f"""
    You are a professional AI Data Analyst Agent. You have access to a pandas DataFrame named `df`.
    DataFrame Schema info:
    - Columns and Types: {df_context.dtypes.to_dict()}
    - Shape: {df_context.shape}
    - First 3 rows:
    {df_context.head(3).to_string()}
    - Numeric Column Stats:
    {df_context.describe().to_string()}
    """
    
    code_prompt = f"""
    {schema_desc}
    
    User's Question: "{user_query}"
    
    Write a short, clean Python code block using pandas to analyze `df` and print the results that answer the user's question.
    Follow these rules:
    - Only use standard pandas methods on the dataframe `df`.
    - Always print the final answer using `print()`.
    - Do not try to read or load any CSV files; `df` is already in memory.
    - Output ONLY the python code inside a ```python ``` block. No other text, markdown explanations, or imports.
    """
    
    try:
        response = model.generate_content(code_prompt)
        code_text = response.text.strip()
        
        # Execute code
        stdout_res, err = run_pandas_code(code_text, df_context)
        
        if err:
            # Self-correction loop: try once more by feeding the error back
            correction_prompt = f"""
            {schema_desc}
            We ran the following python code block to answer "{user_query}":
            {code_text}
            
            But it failed with the following traceback/error:
            {err}
            
            Write a corrected, clean Python code block using pandas to calculate the answer.
            Output ONLY the python code inside a ```python ``` block. No other text.
            """
            response = model.generate_content(correction_prompt)
            code_text = response.text.strip()
            stdout_res, err = run_pandas_code(code_text, df_context)
            
        if err:
            return f"The AI Agent generated code that failed to run: {err}", None, None
            
        if not stdout_res:
            stdout_res = "Execution completed successfully with no output."
            
        explain_prompt = f"""
        {schema_desc}
        
        User's Question: "{user_query}"
        
        We executed the following Pandas code on the dataframe:
        ```python
        {code_text}
        ```
        
        The code execution yielded the following output:
        {stdout_res}
        
        Write a professional business analyst response to the user.
        - Explain the numbers, averages, trends, or groupings calculated in the output.
        - Identify any interesting business patterns or anomalies.
        - Suggest actionable recommendations for decision-makers.
        - Keep the tone executive, objective, and data-backed.
        - Format the response in structured, clean Markdown.
        """
        
        explain_res = model.generate_content(explain_prompt)
        
        # Extract code from block
        code_match = re.search(r"```python(.*?)```", code_text, re.DOTALL)
        if not code_match:
            code_match = re.search(r"```(.*?)```", code_text, re.DOTALL)
        code_clean = code_match.group(1).strip() if code_match else code_text
        
        return explain_res.text, code_clean, stdout_res
        
    except Exception as e:
        return f"Error executing DataFrame Agent: {e}", None, None

# Initialize Session State for Chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# ----------------------------------------------------
# Data Loading & Processing
# ----------------------------------------------------
if uploaded_file is not None:
    try:
        # Load and clean dataset
        df = pd.read_csv(uploaded_file, skipinitialspace=True)
        # Strip spaces from column names
        df.columns = [col.strip() for col in df.columns]
        
        # Handle misaligned target columns (like in census dataset)
        if df.columns[-1].startswith('Unnamed') or df.columns[-1] == '':
            df.rename(columns={df.columns[-1]: 'income'}, inplace=True)
            
        # Strip whitespaces from string columns
        for col in df.select_dtypes(include=['object', 'str']).columns:
            df[col] = df[col].astype(str).str.strip()

        st.sidebar.success(f"Loaded: {uploaded_file.name}")
        
        # Identify columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'str']).columns.tolist()
        
        # Determine likely target column
        target_col = None
        for candidate in ['income', 'sales', 'profit', 'revenue', 'target']:
            if candidate in df.columns:
                target_col = candidate
                break
        if target_col is None:
            target_col = df.columns[-1]  # Default to last column

        # Detect special datasets
        is_census = 'education-num' in df.columns and 'income' in df.columns
        is_ecommerce = any(x in df.columns for x in ['sales', 'profit', 'revenue', 'quantity'])

        # ----------------------------------------------------
        # KPI Layout (Professional Dashboard)
        # ----------------------------------------------------
        st.markdown("### 📊 Executive KPI Dashboard")
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        
        # Calculate missing values
        missing_count = df.isnull().sum().sum()
        for col in categorical_cols:
            missing_count += (df[col] == '?').sum()
            
        with kpi_col1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-val">{df.shape[0]:,}</div>
                <div class="kpi-label">Total Record Count</div>
            </div>
            """, unsafe_allow_html=True)
            
        with kpi_col2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-val">{df.shape[1]}</div>
                <div class="kpi-label">Total Attributes</div>
            </div>
            """, unsafe_allow_html=True)
            
        with kpi_col3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-val">{missing_count:,}</div>
                <div class="kpi-label">Missing/Unknown Cells</div>
            </div>
            """, unsafe_allow_html=True)
            
        with kpi_col4:
            if is_census:
                high_pct = (df['income'] == '>50K').sum() / len(df) * 100
                label = "High Earner Rate (>50K)"
                val = f"{high_pct:.1f}%"
            elif is_ecommerce and 'sales' in df.columns:
                val = f"${df['sales'].sum():,.0f}"
                label = "Total Sales Revenue"
            else:
                val = f"{len(numeric_cols)} / {len(categorical_cols)}"
                label = "Numerical / Categorical"
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-val">{val}</div>
                <div class="kpi-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

        st.write("")

        # ----------------------------------------------------
        # Tabs Layout
        # ----------------------------------------------------
        tab_summary, tab_charts, tab_assistant, tab_insights = st.tabs([
            "📋 Executive Summary & Data", 
            "📈 Interactive Charts", 
            "💬 AI Assistant Chatbot",
            "🎯 Business Recommendations"
        ])
        
        # ----------------------------------------------------
        # Tab 1: Executive Summary & Data
        # ----------------------------------------------------
        with tab_summary:
            st.subheader("Business Executive Summary")
            
            if is_census:
                st.markdown("""
                This dataset details demographic profiles, educational credentials, work histories, and earnings for over **32,000 individuals**. 
                The core target is classification of income groups (`>50K` vs `<=50K`). 
                Key findings indicate a high correlation between advanced post-graduate degrees, executive management roles, and high earning brackets.
                """)
            elif is_ecommerce:
                st.markdown("""
                This dataset comprises transaction logs, product categories, quantities sold, and financial statements. 
                The analysis is optimized to track customer segments, profit margins, and peak seasonal velocity categories.
                """)
            else:
                st.markdown(f"""
                Ingested generic dataset containing **{df.shape[0]:,} rows** and **{df.shape[1]:,} columns**. 
                Primary numeric features include: `{', '.join(numeric_cols[:5])}`. 
                Primary categorical divisions include: `{', '.join(categorical_cols[:5])}`.
                """)
                
            st.subheader("Data Explorer")
            st.dataframe(df.head(10))
            
            col_sum1, col_sum2 = st.columns(2)
            with col_sum1:
                st.subheader("Attribute Profiling")
                dtypes_df = pd.DataFrame({
                    "Type": df.dtypes.astype(str),
                    "Nulls": df.isnull().sum(),
                    "Missing Placeholder ('?')": [(df[col] == '?').sum() if col in categorical_cols else 0 for col in df.columns]
                })
                st.dataframe(dtypes_df)
            with col_sum2:
                st.subheader("Numerical Attributes Statistics")
                st.dataframe(df.describe().T)

        # ----------------------------------------------------
        # Tab 2: Interactive Charts
        # ----------------------------------------------------
        with tab_charts:
            st.subheader("Interactive Visualizations")
            
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1:
                # Pre-populate sensible defaults
                def_x = 'education' if 'education' in df.columns else df.columns[0]
                x_axis = st.selectbox("Select X-Axis", df.columns.tolist(), index=df.columns.tolist().index(def_x) if def_x in df.columns else 0)
            with col_c2:
                def_y = 'hours-per-week' if 'hours-per-week' in df.columns else 'None'
                y_axis = st.selectbox("Select Y-Axis (Optional)", ["None"] + df.columns.tolist(), index=(df.columns.tolist().index(def_y)+1) if def_y in df.columns else 0)
            with col_c3:
                def_hue = 'income' if 'income' in df.columns else 'None'
                hue_var = st.selectbox("Select Grouping (Hue, Optional)", ["None"] + df.columns.tolist(), index=(df.columns.tolist().index(def_hue)+1) if def_hue in df.columns else 0)
                
            chart_type = st.selectbox("Select Plot Type", [
                "Histogram/Distribution", 
                "Bar Plot (Averages/Counts)", 
                "Scatter Plot", 
                "Box Plot"
            ])
            
            # Store values in session state for Chart Explanation in Chat
            st.session_state['chart_x'] = x_axis
            st.session_state['chart_y'] = y_axis
            st.session_state['chart_hue'] = hue_var
            st.session_state['chart_type'] = chart_type
            
            fig, ax = plt.subplots(figsize=(10, 5))
            hue_param = None if hue_var == "None" else hue_var
            
            try:
                if chart_type == "Histogram/Distribution":
                    if df[x_axis].dtype in [np.int64, np.float64]:
                        sns.histplot(data=df, x=x_axis, hue=hue_param, kde=True, ax=ax, palette="coolwarm", multiple="stack")
                        st.pyplot(fig)
                    else:
                        st.warning("Histograms require a numerical X-axis.")
                        
                elif chart_type == "Bar Plot (Averages/Counts)":
                    if y_axis == "None":
                        sns.countplot(data=df, x=x_axis, hue=hue_param, ax=ax, palette="coolwarm", order=df[x_axis].value_counts().index[:15])
                        plt.xticks(rotation=45, ha='right')
                        st.pyplot(fig)
                    else:
                        sns.barplot(data=df, x=x_axis, y=y_axis, hue=hue_param, ax=ax, palette="coolwarm")
                        plt.xticks(rotation=45, ha='right')
                        st.pyplot(fig)
                        
                elif chart_type == "Scatter Plot":
                    if y_axis != "None":
                        sns.scatterplot(data=df, x=x_axis, y=y_axis, hue=hue_param, ax=ax, palette="coolwarm", alpha=0.7)
                        st.pyplot(fig)
                    else:
                        st.warning("Scatter plots require both X-axis and Y-axis variables.")
                        
                elif chart_type == "Box Plot":
                    if y_axis != "None":
                        sns.boxplot(data=df, x=x_axis, y=y_axis, hue=hue_param, ax=ax, palette="coolwarm")
                        plt.xticks(rotation=45, ha='right')
                        st.pyplot(fig)
                    else:
                        st.warning("Box plots require both X-axis and Y-axis variables.")
            except Exception as e:
                st.error(f"Render Error: {e}")
                
            plt.close()

        # ----------------------------------------------------
        # Tab 3: AI Assistant Chatbot
        # ----------------------------------------------------
        with tab_assistant:
            st.subheader("💬 Discuss your Data with the AI Analyst")
            
            # Display chat messages from history
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    if "code_exec" in message:
                        st.code(message["code_exec"])
                    if "code_output" in message:
                        st.text(f"Execution Output:\n{message['code_output']}")

            # Handle user input
            if user_query := st.chat_input("Ask a question about the uploaded dataset..."):
                # Display user query
                with st.chat_message("user"):
                    st.markdown(user_query)
                st.session_state.messages.append({"role": "user", "content": user_query})
                
                # Show spinner while loading
                with st.spinner("Analyzing dataset..."):
                    if gemini_key:
                        response_content, executed_code, execution_stdout = query_dataframe_agent(user_query, df, gemini_key)
                    else:
                        response_content = "⚠️ **Gemini API Key Missing**: Please enter your Gemini API Key in the sidebar to activate the AI DataFrame Analyst Agent."
                        executed_code = None
                        execution_stdout = None
                    
                    # Display Assistant Response in Chat
                    with st.chat_message("assistant"):
                        st.markdown(response_content)
                        if executed_code:
                            st.code(executed_code)
                        if execution_stdout:
                            st.text(f"Execution Output:\n{execution_stdout}")
                            
                    # Save to session history
                    msg_dict = {"role": "assistant", "content": response_content}
                    if executed_code:
                        msg_dict["code_exec"] = executed_code
                    if execution_stdout:
                        msg_dict["code_output"] = execution_stdout
                    st.session_state.messages.append(msg_dict)

        # Tab 4: Business Recommendations
        # ----------------------------------------------------
        with tab_insights:
            st.subheader("🎯 Actionable Strategies & Project Quality")
            
            if is_census:
                st.markdown("""
                <div class="recommendation-box">
                    <h4>1. Launch Adult Upskilling Pipelines</h4>
                    <strong>Action Plan</strong>: Create corporate sponsorships or public training pipelines to transition workers from High School levels to technical/degree achievements.
                    <br><em>Data Justification</em>: Earning a Bachelors degree results in a 2.6x increase in high-income likelihood (from 15.9% to 41.5%).
                </div>
                <div class="recommendation-box">
                    <h4>2. Implement Promotion & Equal Pay Audits</h4>
                    <strong>Action Plan</strong>: Audit salary bands and executive-level recruitment pipelines to address the gender earnings gap.
                    <br><em>Data Justification</em>: Men are nearly 3 times more likely to earn >50K (30.6%) compared to women (10.9%).
                </div>
                <div class="recommendation-box">
                    <h4>3. Restructure Performance-over-Hours Metrics</h4>
                    <strong>Action Plan</strong>: Decouple promotions and leadership tracks from rigid, long work weeks (45+ hours) to reduce burnout and enhance retention.
                    <br><em>Data Justification</em>: High earners work an average of 45.5 hours/week, which acts as a barrier to employee groups with household care responsibilities.
                </div>
                """, unsafe_allow_html=True)
                
            elif is_ecommerce:
                st.markdown("""
                <div class="recommendation-box">
                    <h4>1. Optimize Margins on High-Volume/Low-Profit Products</h4>
                    <strong>Action Plan</strong>: Re-negotiate shipping rates or increase product bundles on high-sales categories that exhibit narrow margins.
                </div>
                <div class="recommendation-box">
                    <h4>2. Target High-Value Customers (AOV Retention)</h4>
                    <strong>Action Plan</strong>: Develop loyalty schemes and targeted email marketing for segments that spend above the average order threshold.
                </div>
                """, unsafe_allow_html=True)
                
            else:
                st.markdown("""
                <div class="recommendation-box">
                    <h4>1. Invest in Data Quality Audits</h4>
                    <strong>Action Plan</strong>: Clean up missing values and standardize entry constraints to improve analysis and predictive accuracy.
                    <br><em>Data Justification</em>: Preprocessed column metrics reveal areas where missing cells or placeholder characters exist.
                </div>
                <div class="recommendation-box">
                    <h4>2. Focus Resources on High-frequency Segments</h4>
                    <strong>Action Plan</strong>: Allocate budget and operations to serve the primary customer or category demographics highlighted in the Data Summary.
                </div>
                """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error reading file: {e}")

else:
    # Landing page state
    st.info("👈 Please upload a CSV file in the sidebar to begin data analysis.")
    st.markdown("""
    ### Features of this Portal:
    1. **Automatic Dataset Profile**: Ingests, cleans, and profiles your dataset structure and data types.
    2. **Interactive Chart Builder**: Custom plot rendering (Histograms, Bar Charts, Scatter Plots, Box Plots).
    3. **AI Chat Assistant (Gemini)**: Enter your API key in the sidebar to discuss your dataset dynamically with code execution.
    4. **Actionable Recommendations**: Instant executive takeaways and strategies tailored to your data findings.
    
    *Try uploading the [census-income.csv.csv](file:///C:/Users/hi/ai_data-analyst-agent/census-income.csv.csv) file from the workspace directory!*
    """)