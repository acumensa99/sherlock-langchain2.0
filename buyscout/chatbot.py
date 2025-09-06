import os
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain.agents.agent_types import AgentType
import ast
import datetime

from models.queries import get_seller_data


if "GROQ_API_KEY" not in os.environ:
    raise ValueError("Please set your GROQ_API_KEY in the .env file or environment variables")


def parse_ecommerce_data(data_string):
    try:
        if data_string.endswith("</document_content>"):
            data_string = data_string.replace("</document_content>", "")

        data = ast.literal_eval(data_string)

        df = pd.DataFrame(data)
        return df

    except Exception as e:
        print(f"Error parsing data: {e}")
        try:
            start_idx = data_string.find('[')
            end_idx = data_string.rfind(']')

            if start_idx != -1 and end_idx != -1:
                cleaned_data = data_string[start_idx:end_idx + 1]
                cleaned_data = cleaned_data.replace("None", "null")
                import json
                data = json.loads(cleaned_data)
                df = pd.DataFrame(data)
                return df
        except Exception as nested_e:
            print(f"Fallback parsing failed: {nested_e}")

        # If all parsing fails, create a basic DataFrame from what appears to be structured data
        import re
        pattern = r"'([^']+)': ([^,}]+)"
        matches = re.findall(pattern, data_string)

        sample_data = {}
        for key, value in matches[:20]:  # Just to create a schema
            sample_data[key] = value

        return pd.DataFrame([sample_data])


class EcommerceAnalyzer:
    def __init__(self, model_name="llama3-8b-8192"):
        """Initialize the E-commerce Analyzer with the specified model."""
        # Initialize the Groq LLM
        self.llm = ChatGroq(
            model="llama3-8b-8192",
            groq_api_key=os.environ["GROQ_API_KEY"],
            # temperature=0,
        )
        self.df = None
        self.agent = None

    def load_data(self, data):
        """Load data from a string, CSV file, or create sample data."""

        self.df = data
        # Clean and prepare the data
        self._prepare_data()

        # Display basic info about the data
        print(f"\nDataset shape: {self.df.shape}")
        print("\nColumns:", self.df.columns.tolist())
        print("\nFirst 5 rows:")
        print(self.df.head())
        print("\nData types:")
        print(self.df.dtypes)
        print("\nSummary statistics:")
        print(self.df.describe())

        # Create the pandas dataframe agent
        self.agent = create_pandas_dataframe_agent(
            llm=self.llm,
            df=self.df,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            allow_dangerous_code=True,

            max_iterations=8  # Limit the number of iterations to avoid excessive API calls
        )

        return self.df

    def _prepare_data(self):
        """Clean and prepare the data for analysis"""
        if self.df is None:
            return

        # Convert date strings to datetime if needed
        if 'Date' in self.df.columns and not pd.api.types.is_datetime64_any_dtype(self.df['Date']):
            try:
                self.df['Date'] = pd.to_datetime(self.df['Date'])
            except:
                pass  # Skip if conversion fails

        # Handle potential numeric columns
        numeric_cols = ['Final Price', 'Winner Final Price', 'Ratings', 'Winner Rating',
                        'Delivery Time', 'Winner Delivery']

        for col in numeric_cols:
            if col in self.df.columns and not pd.api.types.is_numeric_dtype(self.df[col]):
                try:
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                except:
                    pass  # Skip if conversion fails

        # Create derived columns for analysis
        if all(col in self.df.columns for col in ['Final Price', 'Winner Final Price']):
            self.df['Price_Difference'] = self.df['Winner Final Price'] - self.df['Final Price']
            self.df['Price_Difference_Percent'] = (self.df['Price_Difference'] / self.df['Final Price']) * 100

        if all(col in self.df.columns for col in ['Delivery Time', 'Winner Delivery']):
            self.df['Delivery_Advantage'] = self.df['Winner Delivery'] - self.df['Delivery Time']

    def query(self, question):
        """Query the agent with a question about the e-commerce data."""
        if self.agent is None:
            raise ValueError("No data loaded. Please load data first.")

        try:
            print("Sending query to Groq API...")
            # question = question + "Use python_repl_ast NOT [python_repl_ast]."
            result = self.agent.invoke(question)
            print(f"Received response: {result}")
            return result
        except Exception as e:
            print(f"Error during query: {str(e)}")
            return f"Error: {str(e)}"

    def visualize_data(self, chart_type="product_category_distribution"):
        """Create visualizations of the e-commerce data."""
        if self.df is None:
            raise ValueError("No data loaded. Please load data first.")

        plt.figure(figsize=(12, 6))

        if chart_type == "product_category_distribution":
            if 'Product Category' in self.df.columns:
                category_counts = self.df['Product Category'].value_counts()
                category_counts.plot(kind='bar', color='skyblue')
                plt.title('Distribution of Products by Category')
                plt.xlabel('Product Category')
                plt.ylabel('Count')
                plt.xticks(rotation=45)
                plt.tight_layout()
            else:
                print("Product Category column not found")

        elif chart_type == "brand_distribution":
            if 'Brand Name' in self.df.columns:
                brand_counts = self.df['Brand Name'].value_counts().head(10)
                brand_counts.plot(kind='bar', color='lightgreen')
                plt.title('Top 10 Brands by Product Count')
                plt.xlabel('Brand')
                plt.ylabel('Count')
                plt.xticks(rotation=45)
                plt.tight_layout()
            else:
                print("Brand Name column not found")

        elif chart_type == "price_distribution":
            if 'Final Price' in self.df.columns:
                plt.hist(self.df['Final Price'].dropna(), bins=20, color='coral', alpha=0.7)
                plt.title('Distribution of Product Prices')
                plt.xlabel('Price')
                plt.ylabel('Frequency')
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
            else:
                print("Final Price column not found")

        elif chart_type == "buybox_analysis":
            if 'Lost Buybox' in self.df.columns:
                buybox_counts = self.df['Lost Buybox'].value_counts()
                buybox_counts.plot(kind='pie', autopct='%1.1f%%', colors=['lightgreen', 'coral'])
                plt.title('Buy Box Win/Loss Analysis')
                plt.axis('equal')
                plt.tight_layout()
            else:
                print("Lost Buybox column not found")

        elif chart_type == "rating_vs_price":
            if all(col in self.df.columns for col in ['Ratings', 'Final Price']):
                plt.scatter(self.df['Ratings'].dropna(), self.df['Final Price'].dropna(),
                            alpha=0.7, color='purple')
                plt.title('Product Ratings vs. Price')
                plt.xlabel('Rating')
                plt.ylabel('Price')
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
            else:
                print("Ratings or Final Price columns not found")

        else:
            raise ValueError(f"Unknown chart type: {chart_type}")

        plt.show()
        return plt

    def generate_buybox_insights(self):
        """Generate insights related to Buy Box performance"""
        if self.df is None:
            raise ValueError("No data loaded. Please load data first.")

        insights = {}

        # Calculate Buy Box win rate
        if 'Lost Buybox' in self.df.columns:
            total_products = len(self.df)
            won_buybox = len(self.df[self.df['Lost Buybox'] == False])
            win_rate = won_buybox / total_products * 100
            insights['win_rate'] = f"{win_rate:.2f}%"
            insights['total_products'] = total_products
            insights['won_buybox'] = won_buybox
            insights['lost_buybox'] = total_products - won_buybox

        # Analyze price difference in lost Buy Box cases
        if all(col in self.df.columns for col in ['Lost Buybox', 'Price_Difference']):
            lost_df = self.df[self.df['Lost Buybox'] == True]
            if not lost_df.empty:
                avg_price_diff = lost_df['Price_Difference'].mean()
                insights['avg_price_difference'] = avg_price_diff
                insights['max_price_difference'] = lost_df['Price_Difference'].max()
                insights['min_price_difference'] = lost_df['Price_Difference'].min()

        # Analyze delivery time difference in lost Buy Box cases
        if all(col in self.df.columns for col in ['Lost Buybox', 'Delivery_Advantage']):
            lost_df = self.df[self.df['Lost Buybox'] == True]
            if not lost_df.empty:
                avg_delivery_diff = lost_df['Delivery_Advantage'].mean()
                insights['avg_delivery_difference'] = avg_delivery_diff

        # Analyze by category
        if 'Product Category' in self.df.columns and 'Lost Buybox' in self.df.columns:
            category_performance = {}
            for category in self.df['Product Category'].dropna().unique():
                category_df = self.df[self.df['Product Category'] == category]
                total = len(category_df)
                won = len(category_df[category_df['Lost Buybox'] == False])
                win_rate = won / total * 100 if total > 0 else 0
                category_performance[category] = f"{win_rate:.2f}%"
            insights['category_performance'] = category_performance

        return insights


def run_inference(data):
    print("Initializing E-commerce Data Analyzer...")
    analyzer = EcommerceAnalyzer()

    # Load data from the provided string
    analyzer.load_data(data=data)

    questions = [
        "What is the total number of products in the dataset?",
        # "What is the distribution of products across different categories?",
        "What is the buy box win rate for 'Happy Ecom'?",
        "Which brand has the highest average price?",
        # "Is there a correlation between delivery time and winning the buy box?",
        "What is the price difference between our seller and competitors when we lose the buy box?"
    ]

    print("\n=== Analysis Results ===")
    for question in questions:
        print(f"\nQ: {question}")
        try:
            answer = analyzer.query(question)
            print(f"A: {answer}")
        except Exception as e:
            print(f"Error analyzing question: {e}")

    print("\n=== Buy Box Performance Insights ===")
    insights = analyzer.generate_buybox_insights()
    for key, value in insights.items():
        print(f"{key}: {value}")

    print("\nGenerating visualizations...")
    analyzer.visualize_data("product_category_distribution")
    analyzer.visualize_data("price_distribution")
    analyzer.visualize_data("buybox_analysis")


if __name__ == "__main__":
    load_dotenv()
    data_string = get_seller_data("Happy Ecom")
