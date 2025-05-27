import streamlit as st
import pandas as pd
import yaml
import requests
import uuid
import numpy as np
import time

st.title("KoBoToolbox Data Migration App")

# Step 1: Upload files
st.header("1. Upload Files")
old_file = st.file_uploader("Upload Old Data CSV", type=["csv"])
xls_file = st.file_uploader("Upload New Form XLSForm (.xlsx)", type=["xlsx"])

if old_file and xls_file:
    old_df = pd.read_csv(old_file, sep=None, engine='python')
    old_fields = list(old_df.columns)

    # Read survey sheet from XLSForm
    xls = pd.ExcelFile(xls_file)
    if 'survey' in xls.sheet_names:
        survey_df = pd.read_excel(xls, sheet_name='survey')
        new_fields = survey_df['name'].dropna().astype(str).tolist()
    else:
        st.error("No 'survey' sheet found in XLSForm.")
        st.stop()

    # Step 2: Interactive mapping
    st.header("2. Map Fields")
    mapping = {}
    for old in old_fields:
        dest = st.selectbox(f"Map '{old}' to:", [""] + new_fields, key=old)
        if dest:
            mapping[old] = dest

    st.header("3. Add New Fields (Optional)")
    add_fields = {}
    new_field = st.text_input("Field name to add")
    new_value = st.text_input("Default value (leave blank for null)")
    if st.button("Add Field"):
        if new_field:
            add_fields[new_field] = None if new_value == "" else new_value
            st.success(f"Added field: {new_field}")

    # Step 3: Save mapping
    st.header("4. Save Mapping")
    if st.button("Save Mapping"):
        yaml_dict = {"fields": mapping}
        if add_fields:
            yaml_dict["add_fields"] = add_fields
        yaml_str = yaml.dump(yaml_dict, sort_keys=False, allow_unicode=True)
        st.code(yaml_str, language="yaml")
        st.download_button("Download mapping.yaml", yaml_str, file_name="mapping.yaml")
        st.session_state['mapping'] = yaml_dict
    else:
        # If not saved yet, use current mapping
        yaml_dict = {"fields": mapping}
        if add_fields:
            yaml_dict["add_fields"] = add_fields

    # Step 4: API details
    st.header("5. Enter KoBoToolbox API Details")
    api_token = st.text_input("API Token", type="password")
    form_id = st.text_input("Form ID")

    # --------------------------------------------------------------
    # Apply mapping to dataframe for preview and validation
    field_mapping = yaml_dict['fields']
    add_fields_map = yaml_dict.get('add_fields', {})
    df = old_df.rename(columns=field_mapping)
    for field, value in add_fields_map.items():
        df[field] = value
    df = df.replace({np.nan: None})

    st.header("6. Preview Mapped Data")
    if st.button("Show Preview"):
        st.dataframe(df.head(10))
        st.session_state['previewed'] = True

    # Extract required fields from XLSForm
    required_fields = []
    if 'required' in survey_df.columns:
        required_fields = survey_df[survey_df['required'] == True]['name'].dropna().astype(str).tolist()

    # Check for missing required fields in mapped DataFrame
    missing_fields = [f for f in required_fields if f not in df.columns]
    if missing_fields:
        st.warning(f"Missing required fields in mapped data: {missing_fields}")
    else:
        st.info("All required fields are present in mapped data.")

    # Check for missing values in required fields
    for field in required_fields:
        if field in df.columns:
            missing_count = df[field].isnull().sum()
            if missing_count > 0:
                st.warning(f"{missing_count} missing values in required field '{field}'.")

    proceed = st.checkbox("I have reviewed the preview and want to proceed with migration")
        
    # ----------------------------------------------------------------


    # Step 5: Run migration

    if proceed:
        if st.button("Run Migration"):
            if not api_token or not form_id:
                st.error("Please enter both API Token and Form ID.")
                st.stop()

            records = df.to_dict(orient='records')

            headers = {
                'Authorization': f'Token {api_token}',
                'Content-Type': 'application/json'
            }
            url = 'https://kc.kobotoolbox.org/api/v1/submissions'


            # --- Batching ---
            batch_size = st.number_input("Batch size", min_value=1, max_value=100, value=10)
            total = len(records)
            status_list = []
            failed = False

            st.write("Submitting records...")

            # st.write("Submitting records...")
            # status_list = []



            # Create a progress bar

            progress = st.progress(0)
            for start in range(0, total, batch_size):
                end = min(start + batch_size, total)
                batch = records[start:end]
                for i, record in enumerate(batch, start=start):
                    record['meta'] = {"instanceID": f"uuid:{uuid.uuid4()}"}
                    submission = {
                        "id": form_id,
                        "submission": record
                    }
                    response = requests.post(url, headers=headers, json=submission)
                    status_msg = f"Row {i+1}: Status {response.status_code} - {response.text}"
                    status_list.append(status_msg)
                    if response.status_code != 201:
                        failed = True
                progress.progress(min(end / total, 1.0))
                time.sleep(0.5)  # Optional: pause between batches

            if failed:
                st.error("Migration Failed. Some records were not submitted successfully.")
            else:
                st.success("Migration Complete!")

            # Store status_list in session state for later access
            st.session_state['status_list'] = status_list

            # if st.button("Show Status Log"):
            #     for msg in status_list:
            #         st.write(msg)
            #     st.download_button("Download Status Log", "\n".join(status_list), file_name="status_log.txt")
    
        # Show Status Log button (after migration)
        if 'status_list' in st.session_state and st.button("Show Status Log"):
            for msg in st.session_state['status_list']:
                st.write(msg)
            st.download_button("Download Status Log", "\n".join(st.session_state['status_list']), file_name="status_log.txt")
    
    else:
        st.info("Please review the preview and check the box to proceed with migration.")

else:
    st.info("Please upload both the old data CSV and the new XLSForm to continue.")
