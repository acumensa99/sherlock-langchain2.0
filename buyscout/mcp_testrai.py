import os
import json
import logging
import uuid
from typing import List, Dict
from sqlalchemy import create_engine, text
from langchain_aws import ChatBedrock
from langchain_core.prompts import PromptTemplate
from mcp.server.fastmcp import FastMCP

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("testrai_mcp")

# Initialize MCP Server
mcp = FastMCP("TestRAI - Test Case Generator")

# ================= CONFIGURATION =================

# Database Setup (PostgreSQL)
engine = create_engine("postgresql://neondb_owner:npg_OwEd9SNe8AKr@ep-weathered-leaf-a1erpfh5-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

# Bedrock Model Setup
try:
    llm_testgen = ChatBedrock(
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name="us-east-1",
        model_kwargs={"temperature": 0.7}
    )
except Exception as e:
    logger.warning(f"Bedrock init failed: {e}")
    llm_testgen = None

# ================= PROMPTS =================

TEST_CASE_GENERATION_PROMPT = """
You are an expert QA engineer specializing in comprehensive test case generation for web applications.

Given:
- URL: {url}
- Testing Requirements: {requirements}

Generate detailed, actionable test cases following this structure:

Test Case Format:
- test_case_number: Sequential number (1, 2, 3, ...)
- test_step: Clear, detailed description of what action to perform
- expected_result: Specific, measurable expected outcome
- status: Always set to "pending"

Requirements for Test Cases:
1. Cover functional testing (navigation, forms, buttons, links)
2. Include UI/UX validation (page load, visual elements, responsiveness)
3. Add integration testing (API calls, third-party services, data flow)
4. Include security checks (authentication, authorization, data validation)
5. Add performance considerations (page load time, resource loading)
6. Test error handling (invalid inputs, edge cases, boundary conditions)
7. Verify data persistence and state management
8. Test cross-browser compatibility considerations
9. Include accessibility checks (ARIA labels, keyboard navigation)
10. Add mobile responsiveness tests

Generate at least 10-15 comprehensive test cases covering different aspects of the application.

Output Format (JSON array):
[
  {{
    "test_case_number": 1,
    "test_step": "Navigate to the specified URL: {url}",
    "expected_result": "The page loads completely without any display errors, showing main content and navigation elements.",
    "status": "pending"
  }},
  ...
]

Return ONLY the JSON array, no markdown, no additional text.
"""

# ================= HELPER FUNCTIONS =================

def generate_test_cases(url: str, requirements: str) -> List[Dict]:
    """Generate test cases using Claude"""
    if not llm_testgen:
        raise Exception("LLM not initialized")
    
    prompt = PromptTemplate.from_template(TEST_CASE_GENERATION_PROMPT)
    chain = prompt | llm_testgen
    response = chain.invoke({"url": url, "requirements": requirements})
    
    # Clean response
    content = response.content.strip()
    content = content.replace('```json', '').replace('```', '').strip()
    
    # Parse JSON
    test_cases = json.loads(content)
    return test_cases

def save_test_cases_to_db(session_id: str, test_identifier: str, test_cases: List[Dict]) -> bool:
    """Save generated test cases to database"""
    try:
        with engine.connect() as conn:
            for test_case in test_cases:
                query = text("""
                    INSERT INTO test_cases 
                    (session_id, test_identifier, test_case_number, test_step, expected_result, actual_result, status)
                    VALUES 
                    (:session_id, :test_identifier, :test_case_number, :test_step, :expected_result, :actual_result, :status)
                """)
                
                conn.execute(query, {
                    "session_id": session_id,
                    "test_identifier": test_identifier,
                    "test_case_number": test_case["test_case_number"],
                    "test_step": test_case["test_step"],
                    "expected_result": test_case["expected_result"],
                    "actual_result": test_case.get("actual_result", ""),
                    "status": test_case.get("status", "pending")
                })
            
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving test cases: {str(e)}")
        return False

# ================= MCP TOOL DEFINITION =================

@mcp.tool()
async def generate_test_cases_for_url(url: str, requirements: str) -> str:
    """
    Generates comprehensive test cases for a given URL based on testing requirements.
    
    Use this tool when users want to:
    - Generate test cases for a website or web application
    - Create QA testing scenarios
    - Validate functionality of a URL
    - Create automated testing scripts
    
    Args:
        url: The target URL to test (e.g., "https://www.flipkart.com/")
        requirements: Testing requirements and focus areas (e.g., "Test homepage navigation, 
                     search functionality, and product listing display. Verify API key integration 
                     in source code.")
    
    Returns:
        JSON string containing generated test cases with test steps, expected results, and status.
    """
    logger.info(f"Generating test cases for URL: {url}")
    logger.info(f"Requirements: {requirements}")
    
    try:
        # Generate unique identifiers
        session_id = str(uuid.uuid4())
        test_identifier = url  # Or extract from requirements if specified
        
        # Generate test cases
        test_cases = generate_test_cases(url, requirements)
        logger.info(f"Generated {len(test_cases)} test cases")
        
        # Save to database
        save_success = save_test_cases_to_db(session_id, test_identifier, test_cases)
        
        if not save_success:
            logger.warning("Failed to save test cases to database")
        
        # Format response
        response = {
            "session_id": session_id,
            "url": url,
            "total_test_cases": len(test_cases),
            "test_cases": test_cases,
            "saved_to_db": save_success
        }
        
        # Create human-readable summary
        summary = f"""
✅ Successfully generated {len(test_cases)} test cases for: {url}

📋 Test Session ID: {session_id}
🎯 Testing Focus: {requirements[:100]}...

Test Cases Overview:
"""
        for i, tc in enumerate(test_cases[:5], 1):  # Show first 5 in summary
            summary += f"\n{i}. {tc['test_step'][:80]}..."
        
        if len(test_cases) > 5:
            summary += f"\n... and {len(test_cases) - 5} more test cases"
        
        summary += f"\n\n💾 Database Status: {'Saved successfully' if save_success else 'Save failed'}"
        summary += f"\n\n__TESTRAI_DATA_START__{json.dumps(response, default=str)}__TESTRAI_DATA_END__"
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating test cases: {str(e)}")
        return f"❌ Error generating test cases: {str(e)}"

@mcp.tool()
async def get_test_cases_by_session(session_id: str) -> str:
    """
    Retrieves test cases for a specific testing session.
    
    Args:
        session_id: The unique session identifier from a previous test generation
    
    Returns:
        JSON string containing all test cases for the session
    """
    logger.info(f"Retrieving test cases for session: {session_id}")
    
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT session_id, test_identifier, test_case_number, 
                       test_step, expected_result, actual_result, status
                FROM test_cases
                WHERE session_id = :session_id
                ORDER BY test_case_number
            """)
            
            result = conn.execute(query, {"session_id": session_id})
            rows = result.fetchall()
            
            if not rows:
                return f"No test cases found for session: {session_id}"
            
            test_cases = []
            for row in rows:
                test_cases.append({
                    "session_id": row[0],
                    "test_identifier": row[1],
                    "test_case_number": row[2],
                    "test_step": row[3],
                    "expected_result": row[4],
                    "actual_result": row[5],
                    "status": row[6]
                })
            
            response = {
                "session_id": session_id,
                "total_test_cases": len(test_cases),
                "test_cases": test_cases
            }
            
            summary = f"📋 Found {len(test_cases)} test cases for session {session_id}\n\n"
            summary += f"__TESTRAI_DATA_START__{json.dumps(response, default=str)}__TESTRAI_DATA_END__"
            
            return summary
            
    except Exception as e:
        logger.error(f"Error retrieving test cases: {str(e)}")
        return f"❌ Error retrieving test cases: {str(e)}"

# Start the server
if __name__ == "__main__":
    import uvicorn
    
    # Extract the internal FastAPI app from the MCP server
    app = mcp.sse_app()
    
    # Run on port 8010 for TestRAI
    print("Starting TestRAI MCP Server on port 8010...")
    uvicorn.run(app, host="0.0.0.0", port=8010)