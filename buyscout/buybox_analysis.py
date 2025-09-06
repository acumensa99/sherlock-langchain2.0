# Define new regional data
import pandas as pd

# Load the uploaded Excel file
file_path = "happyecom_output.xlsx"
xls = pd.ExcelFile(file_path)

# Display the sheet names to understand the structure
sheet_names = xls.sheet_names

# Load the data from the only sheet
df = xls.parse('Sheet1')

# Display the first few rows to understand the structure
df.head()

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USERNAME = "mis@happyecom.com"
SMTP_PASSWORD = "Rakhi@333"

region_data = {
    'North': {'Pincode': 110001, 'Latitude': 28.6139, 'Longitude': 77.2090},
    'South': {'Pincode': 600001, 'Latitude': 13.0827, 'Longitude': 80.2707},
    'East': {'Pincode': 700001, 'Latitude': 22.5726, 'Longitude': 88.3639},
    'West': {'Pincode': 400001, 'Latitude': 18.9388, 'Longitude': 72.8354},
}

# Assign regions in a repeating pattern across the dataframe
regions = ['North', 'South', 'East', 'West']
df['Region'] = [regions[i % 4] for i in range(len(df))]

# Update pincode, latitude, longitude based on region
for region, values in region_data.items():
    df.loc[df['Region'] == region, 'Pincode'] = values['Pincode']
    df.loc[df['Region'] == region, 'Latitude'] = values['Latitude']
    df.loc[df['Region'] == region, 'Longitude'] = values['Longitude']

# Display updated sample
df[['ASIN', 'Region', 'Pincode', 'Latitude', 'Longitude']].head(8)
df_to_save = df.drop(columns=["Region"])
output_path = "happyecom_output_mul.xlsx"
df_to_save.to_excel(output_path, index=False)