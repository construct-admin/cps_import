import os
import requests
import streamlit as st

try:
    import openai
except ImportError:
    openai = None

PUBLISHED = True
APP_URL = "https://alt-text-bot.streamlit.app/"

APP_TITLE = "Construct HTML Generator"
APP_INTRO = "This micro-app allows you to convert text content into HTML format with tag processing."

SYSTEM_PROMPT = "Convert raw content into properly formatted HTML excluding any DOCTYPE or extraneous header lines. Additionally, replace specific placeholders like '[begin content block]' with corresponding HTML elements."

HTML_ELEMENTS = {
    "[begin content block]": '<div class="dp-content-block dp-padding-direction-tblr dp-margin-direction-tblr">',
    "[end content block]": '</div>',
    "[begin heading]": '<h2 class="dp-heading dp-padding-direction-tblr dp-margin-direction-tblr">',
    "[end heading]": '</h2>',
    "[begin subheading]": '<h3 class="dp-padding-direction-tblr dp-margin-direction-tblr">',
    "[end subheading]": '</h3>',
    "[begin paragraph]": '<p>',
    "[end paragraph]": '</p>',
    "[begin list]": '<ul>',
    "[end list]": '</ul>',
    "[begin list item]": '<li>',
    "[end list item]": '</li>',
    "[begin table]": '<table class="table-bordered default-base-style">',
    "[end table]": '</table>',
    "[begin table row]": '<tr>',
    "[end table row]": '</tr>',
    "[begin table cell]": '<td>',
    "[end table cell]": '</td>',
}


def extract_text_from_uploaded_files(files):
    texts = []
    for file in files:
        ext = file.name.split('.')[-1].lower()
        if ext == 'docx':
            from docx import Document
            doc = Document(file)
            full_text = "\n".join([para.text for para in doc.paragraphs])
            texts.append(full_text)
        elif ext == 'pdf':
            from pypdf import PdfReader
            pdf = PdfReader(file)
            text = "".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            texts.append(text)
        else:
            texts.append(file.read().decode('utf-8'))
    return "\n".join(texts)


def replace_placeholders_with_html(content):
    for placeholder, html_code in HTML_ELEMENTS.items():
        content = content.replace(placeholder, html_code)
    return content


def get_ai_generated_html(prompt):
    openai_api_key = st.secrets.get("OPENAI_API_KEY")
    if not openai_api_key:
        st.error("Missing OpenAI API Key. Please add it to your Streamlit secrets.")
        return None

    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    
    if response.status_code == 200:
        ai_response = response.json()["choices"][0]["message"]["content"].strip("`")
        return replace_placeholders_with_html(ai_response)
    else:
        st.error(f"OpenAI API Error: {response.status_code} - {response.text}")
        return None


def check_or_create_module(module_name, canvas_domain, course_id, headers):
    url = f"https://{canvas_domain}/api/v1/courses/{course_id}/modules"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        modules = response.json()
        for module in modules:
            if module["name"].lower() == module_name.lower():
                return module["id"]
    
    # Create module if not found
    payload = {"module": {"name": module_name, "published": PUBLISHED}}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code in [200, 201]:
        return response.json().get("id")
    return None


def create_or_update_page(page_title, page_body, canvas_domain, course_id, headers):
    url = f"https://{canvas_domain}/api/v1/courses/{course_id}/pages/{page_title.replace(' ', '-').lower()}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        payload = {"wiki_page": {"body": page_body, "published": PUBLISHED}}
        requests.put(url, headers=headers, json=payload)
    else:
        url = f"https://{canvas_domain}/api/v1/courses/{course_id}/pages"
        payload = {"wiki_page": {"title": page_title, "body": page_body, "published": PUBLISHED}}
        requests.post(url, headers=headers, json=payload)


def push_to_canvas(module_title, page_title, page_body, canvas_domain, course_id, access_token):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    module_id = check_or_create_module(module_title, canvas_domain, course_id, headers)
    if not module_id:
        st.error("Module creation failed.")
        return
    create_or_update_page(page_title, page_body, canvas_domain, course_id, headers)
    st.success("Page successfully created or updated in Canvas!")


def main():
    st.set_page_config(page_title="Construct HTML Generator", layout="centered", initial_sidebar_state="expanded")
    st.title(APP_TITLE)
    st.markdown(APP_INTRO)
    
    module_title = st.text_input("Enter the title of your module:")
    page_title = st.text_input("Enter the title of your page:")
    uploaded_files = st.file_uploader("Choose files", type=['docx', 'pdf'], accept_multiple_files=True)
    
    uploaded_text = extract_text_from_uploaded_files(uploaded_files) if uploaded_files else ""
    if uploaded_text:
        st.text_area("Extracted Text", uploaded_text, height=300)
    
    if st.button("Generate HTML"):
        if module_title and page_title and uploaded_text:
            ai_generated_html = get_ai_generated_html(replace_placeholders_with_html(uploaded_text))
            if ai_generated_html:
                st.text_area("AI Response:", ai_generated_html, height=300)
                st.session_state.ai_generated_html = ai_generated_html
            else:
                st.error("AI failed to generate HTML content.")
        else:
            st.error("Please provide all inputs.")
    
    if "ai_generated_html" in st.session_state:
        if st.button("Push to Canvas"):
            push_to_canvas(module_title, page_title, st.session_state.ai_generated_html, st.secrets["CANVAS_DOMAIN"], st.secrets["CANVAS_ID"], st.secrets["CANVAS_ACCESS_TOKEN"])

if __name__ == "__main__":
    main()
