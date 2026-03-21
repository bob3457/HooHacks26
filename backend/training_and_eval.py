import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import joblib

# 1. Load the Data
print("Loading data...")
df = pd.read_csv('data/agriculture-and-farming-dataset/synthetic_farm_borrowers.csv')

# 2. Separate Features (X) and Target (y)
# Drop Borrower_ID (irrelevant) and Stress_Probability (data leakage, since it directly calculates the target)
X = df.drop(columns=['Borrower_ID', 'Stress_Probability', 'Requires_Intervention'])
y = df['Requires_Intervention']

# 3. Define Categorical and Numerical Columns
categorical_cols = ['Crop_Type', 'Irrigation_Type', 'Soil_Type', 'Season']
numerical_cols = ['Farm_Area_Acres', 'Fertilizer_Used_Tons', 'Current_LTV_Ratio', 'Months_Since_Delinquency']

# 4. Create Preprocessing Steps
# - OneHotEncode categorical variables
# - StandardScale numerical variables
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), numerical_cols),
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_cols)
    ])

# 5. Build the Full Pipeline
# This chains the preprocessor directly into the Random Forest model
pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('classifier', RandomForestClassifier(
        n_estimators=100, 
        max_depth=5,        # Keep depth shallow to avoid overfitting on synthetic data
        random_state=42, 
        class_weight='balanced' # Helps if interventions are rare
    ))
])

# 6. Split the Data (80% Train, 20% Test)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# 7. Train the Model
print("Training the pipeline...")
pipeline.fit(X_train, y_train)

# 8. Evaluate the Model
print("\n--- Model Evaluation ---")
y_pred = pipeline.predict(X_test)
y_proba = pipeline.predict_proba(X_test)[:, 1] # Get probability for the "1" (Intervention) class

print("\nConfusion Matrix:")
print(confusion_matrix(y_test, y_pred))

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

roc_auc = roc_auc_score(y_test, y_proba)
print(f"ROC-AUC Score: {roc_auc:.4f}")

# 9. Save the Model for the Web App
# The UI developers will load this exact file to make predictions on the dashboard
model_filename = 'farm_risk_model.joblib'
joblib.dump(pipeline, model_filename)
print(f"\nModel saved successfully as {model_filename}")