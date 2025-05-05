import streamlit as st
import pandas as pd
from main import *

# Page configuration
st.set_page_config(
    page_title="CV Matcher",
    page_icon="📝",
    layout="wide"
)

# Add custom CSS for email preview
st.markdown("""
<style>
.email-preview {
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 20px;
    margin: 10px 0;
}
.accept-email {
    background-color: #f0fff4;
    border-left: 5px solid #4CAF50;
}
.reject-email {
    background-color: #fff5f5;
    border-left: 5px solid #f44336;
}
</style>
""", unsafe_allow_html=True)

# Application title and description
st.title("📝 CV and Job Description Matcher")
st.markdown("""
This application analyzes CVs in PDF format and compares them with job descriptions to determine if there's a good match.
Based on the match, it automatically sends either a congratulations or rejection email to the applicant.
""")

# Initialize session states
if 'application_data' not in st.session_state:
    st.session_state.application_data = []

# Main tabs
tab1, tab2 = st.tabs(["📤 Upload Files", "📊 View Results"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("CV Upload")
        cv_file = st.file_uploader("Upload CV (PDF format)", type="pdf")
        applicant_name = st.text_input("Applicant Name")
        applicant_email = st.text_input("Applicant Email")
    
    with col2:
        st.header("Job Description")
        job_title = st.text_input("Job Title")
        job_description = st.text_area("Job Description", height=250)
        match_threshold = st.slider("Match Threshold (%)", 50, 95, 70)
    
    if st.button("Analyze and Send Email"):
        if not all([cv_file, job_description, applicant_email]):
            st.error("Please fill all required fields")
        else:
            with st.spinner("Processing..."):
                result = process_application(
                    cv_file, applicant_name, applicant_email, 
                    job_title, job_description, match_threshold
                )                
                if result["success"]:
                    st.session_state.application_data.append(result)
                    
                    # Display results
                    st.success("✅ Analysis complete!")
                    
                    # Generate email preview content
                    is_accepted = result["recommendation"] == "Accept"
                    email_subject, email_body = email_content(applicant_name, job_title, is_accepted)
                    
                    # Format email body for HTML display (replace newlines with <br>)
                    formatted_email = email_body.replace("\n", "<br>")
                    
                    # Show email preview
                    if is_accepted:
                        st.markdown(f"""
                        <div class="email-preview accept-email">
                            <h3>🎉 Acceptance Email Preview (Sent to {applicant_email})</h3>
                            <p><strong>Subject:</strong> {email_subject}</p>
                            <hr>
                            <p>{formatted_email}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        st.balloons()
                    else:
                        st.markdown(f"""
                        <div class="email-preview reject-email">
                            <h3>😞 Rejection Email Preview (Sent to {applicant_email})</h3>
                            <p><strong>Subject:</strong> {email_subject}</p>
                            <hr>
                            <p>{formatted_email}</p>
                        </div>
                        """, unsafe_allow_html=True)

with tab2:
    st.header("Application Results")
    
    if not st.session_state.application_data:
        st.info("No applications processed yet")
    else:
        # Create dataframe
        df = pd.DataFrame({
            "Applicant": [app["applicant_name"] for app in st.session_state.application_data],
            "Job Title": [app["job_title"] for app in st.session_state.application_data],
            "Match %": [app["match_percentage"] for app in st.session_state.application_data],
            "Decision": [app["recommendation"] for app in st.session_state.application_data],
            "Email Status": ["✅ Sent" if app["email_sent"] else "❌ Failed" for app in st.session_state.application_data]
        })
        
        # Display with conditional formatting
        def color_decision(val):
            color = '#4CAF50' if val == "Accept" else '#f44336'
            return f'background-color: {color}; color: white'
        
        st.dataframe(
            df.style.applymap(color_decision, subset=["Decision"]),
            use_container_width=True
        )