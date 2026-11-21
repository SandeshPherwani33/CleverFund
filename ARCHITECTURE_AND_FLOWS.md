# 📊 SYSTEM ARCHITECTURE & DATA FLOW

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    STARTUP SUCCESS PREDICTION                   │
│                     ML System with SMOTE                         │
└─────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (UI)                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Dashboard                      Prediction Form                   │
│  ┌─────────────────┐           ┌──────────────────┐              │
│  │ Stats Cards     │           │ Model Toggle     │              │
│  │ Charts          │           │ ┌──────────────┐ │              │
│  │ Analytics       │───────►   │ │ Rule-Based ◆ │ │              │
│  └─────────────────┘           │ └──────────────┘ │              │
│                                │ ┌──────────────┐ │              │
│  Results Panel              ──►│ │ ML (SMOTE+RF)│ │              │
│  ┌─────────────────┐           │ └──────────────┘ │              │
│  │ Probability %   │           │                  │              │
│  │ Risk Score      │           │ Startup Details  │              │
│  │ Confidence      │           │ • Funding        │              │
│  │ Recommendations │           │ • Employees      │              │
│  └─────────────────┘           │ • Industry       │              │
│                                │ • Revenue        │              │
│  Visualizations                │ • Location       │              │
│  ┌─────────────────┐           │                  │              │
│  │ Feature Imp.    │           │ [Predict Button]│              │
│  │ Charts          │           └──────────────────┘              │
│  └─────────────────┘                                              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
    ↓ HTTP Requests                           ↑ JSON Responses
    │                                         │
    ├──POST /predict ───────┐                 │
    ├──POST /api/ml-predict │                 │
    └──POST /api/ml-batch   │                 │
                            │                 │
┌───────────────────────────▼─────────────────┴──────────────────────┐
│                    FLASK BACKEND (app.py)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Endpoint Routers                                                  │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────┐  │
│  │ /predict         │   │ /api/ml-predict  │   │ /api/ml-     │  │
│  │                  │   │                  │   │ batch-predict│  │
│  │ Rule-based       │   │ ML-based         │   │              │  │
│  │ scoring          │   │ SMOTE + RF       │   │ Multiple     │  │
│  └──────────────────┘   └──────────────────┘   │ startups     │  │
│                                                 └──────────────┘  │
│                                                                     │
│  Session Management   │   Prediction History                       │
│  • Login/Logout       │   • Save predictions                       │
│  • Auth checks        │   • Load history                           │
│  • User tracking      │   • Delete entries                         │
│                       │                                             │
└────────────────┬──────────────────────┬─────────────────────────────┘
                 │                      │
                 ▼                      ▼
         ┌─────────────────┐  ┌──────────────────┐
         │  Rule-Based     │  │  ML Predictor    │
         │  Predictor      │  │                  │
         │                 │  │ predict_startup  │
         │ (scoring.py)    │  │ _success.py      │
         └─────────────────┘  └────────┬─────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
           ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
           │  Load Model     │ │ Cold Start      │ │ Feature         │
           │                 │ │ Handler         │ │ Encoding        │
           │ startup_model   │ │                 │ │                 │
           │ .pkl            │ │ Fill missing    │ │ LabelEncode     │
           │                 │ │ Handle unknown  │ │ categorical     │
           └─────────────────┘ └─────────────────┘ └─────────────────┘
                    │                  │                  │
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
                         ┌──────────────────────────┐
                         │  RandomForest Model      │
                         │  (Trained with SMOTE)   │
                         │                          │
                         │  • 100 trees             │
                         │  • max_depth: 15         │
                         │  • Balanced on SMOTE     │
                         │  • Evaluated on original │
                         └──────────────────────────┘
                                       │
                                       ▼
                         ┌──────────────────────────┐
                         │  Return Prediction       │
                         │                          │
                         │  • Probability           │
                         │  • Confidence            │
                         │  • Class label           │
                         │  • Feature importance    │
                         │  • Recommendations       │
                         └──────────────────────────┘
```

## Training Pipeline Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    TRAINING PIPELINE (train.py)                  │
└──────────────────────────────────────────────────────────────────┘

1. DATA LOADING & PREPROCESSING
   ┌──────────────────────┐
   │  CSV FILE            │
   │  • combined_dataset  │
   │  • cleaned_failure   │
   └──────┬───────────────┘
          │
          │  Load & Normalize Columns
          ▼
   ┌──────────────────────┐
   │  Handle Missing      │
   │  • Numeric: median   │
   │  • Categorical: mode │
   └──────┬───────────────┘
          │
          │  Encode Categorical
          ▼
   ┌──────────────────────┐
   │  Preprocessed Data   │
   │  • All nulls handled │
   │  • Categories encoded│
   └─────────────────────┘

2. TRAIN/TEST SPLIT (80/20)
   ┌──────────────────────────────────────────┐
   │         Full Dataset (563 samples)       │
   ├──────────────────────────────────────────┤
   │                                          │
   │  Training: 450 samples     Test: 113     │
   │  (80%)                     (20%)         │
   │                                          │
   └──────────────────────────────────────────┘
          │                        │
          ▼                        │
   ┌──────────────────────┐       │
   │ CLASS DIST BEFORE    │       │
   │ Success:  300 (67%)  │       │
   │ Failure:  150 (33%)  │       │
   └──────┬───────────────┘       │
          │                        │
          │ APPLY SMOTE            │
          │ (Only on training!)    │
          ▼                        │
   ┌──────────────────────┐       │
   │ CLASS DIST AFTER     │       │
   │ Success:  300 (50%)  │       │
   │ Failure:  300 (50%)  │       │
   │ Total:    600 (GREW!)│       │
   └──────┬───────────────┘       │
          │                        │
          │ BALANCED DATA           │
          ├────────────────────────┼──────────┐
          │                        │          │
          ▼                        ▼          │
   ┌──────────────────┐  ┌──────────────────┐│
   │ Train Random     │  │ Test Set         ││
   │ Forest           │  │ (Original dist)  ││
   │                  │  │ Success: 75      ││
   │ • 100 trees      │  │ Failure: 38      ││
   │ • max_depth: 15  │  └──────────────────┘│
   │ • Balanced       │                      │
   └────────┬─────────┘                      │
            │                                 │
            │ FIT MODEL                       │
            │                                 │
            ├─────────────────┬───────────────┘
            │                 │
            ▼                 ▼
   ┌────────────────────────────────┐
   │   EVALUATE ON TEST SET         │
   │                                │
   │ Predictions on original dist   │
   │ • Accuracy: 85%               │
   │ • Precision: 84%              │
   │ • Recall: 87%                 │
   │ • ROC-AUC: 0.85               │
   └────────────────────────────────┘

3. SAVE ARTIFACTS
   ┌──────────────────────────────────────────┐
   │                                          │
   │  models/startup_model.pkl                │
   │  • Trained RandomForest                  │
   │                                          │
   │  models/preprocessing_info.pkl           │
   │  • Label encoders (industry, location)   │
   │  • Feature columns                       │
   │  • Median values (for cold start)        │
   │                                          │
   │  data/training_report.json               │
   │  • Training metrics                      │
   │  • SMOTE info                            │
   │                                          │
   │  static/charts/*.png                     │
   │  • SMOTE comparison                      │
   │  • Feature importance                    │
   │  • Confusion matrix                      │
   │                                          │
   └──────────────────────────────────────────┘
```

## Cold Start Handling Flow

```
NEW PREDICTION REQUEST
        │
        │  Input Data
        │  ┌──────────────────────┐
        │  │ funding_amount: None │ ← Missing
        │  │ employees: 25        │
        │  │ industry: 'NewTech'  │ ← Unknown
        │  │ revenue: None        │ ← Missing
        │  │ location: 'SF'       │
        │  └──────────────────────┘
        │
        ▼
   ┌────────────────────────────────┐
   │   handle_cold_start()          │
   │                                │
   │   For each column:             │
   │   ├─ If numeric & null:        │
   │   │  └─ Fill with median       │
   │   │                            │
   │   ├─ If categorical & null:    │
   │   │  └─ Fill with 'unknown'    │
   │   │                            │
   │   └─ If unknown category:      │
   │      └─ Encode as 'unknown'    │
   └────────┬──────────────────────┘
            │
            ▼
   ┌──────────────────────────┐
   │ Preprocessed Data        │
   │ ┌──────────────────────┐ │
   │ │ funding: 1,500,000   │ │ ← From median
   │ │ employees: 25        │ │ ← Original
   │ │ industry: 'unknown'  │ │ ← New category
   │ │ revenue: 750,000     │ │ ← From median
   │ │ location: 'SF'       │ │ ← Original
   │ └──────────────────────┘ │
   └────────┬─────────────────┘
            │
            ▼
   ┌──────────────────────────┐
   │ Ready for Prediction     │
   │                          │
   │ → Send to model          │
   │ → Get probability        │
   │ → Return result          │
   └──────────────────────────┘
```

## Model Switching Logic (Frontend)

```
USER INTERACTION
        │
        ├─ View Dashboard
        │
        ├─ Fill Prediction Form
        │
        ├─ Toggle Model Button
        │  ├─ IF OFF → "Rule-Based"
        │  │  └─ useMLModel = false
        │  │
        │  └─ IF ON → "ML (SMOTE+RF)"
        │     └─ useMLModel = true
        │
        ├─ Click "Predict" Button
        │
        ▼
   ┌──────────────────────────┐
   │  handlePredict() JS      │
   │                          │
   │  Gather form data        │
   │  Calculate local scores  │
   │                          │
   │  IF useMLModel:          │
   │   └─ endpoint = "/api/ml-predict"
   │  ELSE:                   │
   │   └─ endpoint = "/predict"
   │                          │
   │  POST to endpoint        │
   │  with JSON payload       │
   └────────┬─────────────────┘
            │
            ├─ RULE_BASED ───────┐
            │                    │
            ▼                    ▼
     ┌────────────────┐  ┌────────────────┐
     │ /predict       │  │ /api/ml-predict│
     │                │  │                │
     │ Weighted score │  │ ML Model       │
     │ • funding: 25  │  │ • Probability  │
     │ • team: 20     │  │ • Confidence   │
     │ • revenue: 25  │  │ • SMOTE-trained│
     │ • industry: 20 │  │                │
     │ • location: 10 │  └────────────────┘
     └────────────────┘          │
            │                    │
            └────────┬───────────┘
                     │
                     │ JSON Response
                     ▼
         ┌───────────────────────┐
         │ Parse Response        │
         │                       │
         │ • probability         │
         │ • result              │
         │ • scores              │
         │ • recommendations     │
         └────────┬──────────────┘
                  │
                  │ Update UI
                  ▼
         ┌───────────────────────┐
         │ Display Results       │
         │                       │
         │ • Ring Chart %        │
         │ • Success/Failure     │
         │ • Risk Score          │
         │ • Recommendations     │
         │ • Feature Chart       │
         └───────────────────────┘
```

## File Dependencies

```
predict_startup_success.py (Prediction Module)
    ├── joblib (load model)
    ├── numpy (arrays)
    ├── pandas (dataframe)
    └── sklearn.preprocessing.LabelEncoder (encoding)

train.py (Training)
    ├── pandas (data loading)
    ├── numpy (math)
    ├── sklearn.ensemble.RandomForestClassifier
    ├── sklearn.preprocessing.LabelEncoder
    ├── sklearn.model_selection.train_test_split
    ├── imblearn.over_sampling.SMOTE
    ├── joblib (save model)
    └── visualizations (charts)

app.py (Flask Backend)
    ├── flask (web framework)
    ├── predict_startup_success (ML predictions)
    ├── dataset.py (data loading)
    └── logging (debug info)

Frontend (templates + JS)
    ├── templates/index.html
    ├── static/js/script.js
    └── static/css/style.css
```

## Database Schema (If Using DB)

```
Predictions Table
┌─────────────────────────────────────┐
│ id (PK)                             │
│ user_id (FK)                        │
│ timestamp                           │
│ startup_name                        │
│ funding_amount                      │
│ num_employees                       │
│ industry                            │
│ revenue                             │
│ location                            │
│ prediction_result (Success/Failure) │
│ probability                         │
│ confidence                          │
│ model_type (Rule-Based / ML)        │
│ preprocessing_params (JSON)         │
└─────────────────────────────────────┘
```

## Deployment Architecture

```
PRODUCTION DEPLOYMENT

┌─────────────────────────────────────────────────────┐
│                  Load Balancer                      │
│              (Nginx / AWS ELB)                      │
└───────────────────────┬─────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
    ┌────────┐     ┌────────┐     ┌────────┐
    │Instance│     │Instance│     │Instance│
    │   1    │     │   2    │     │   3    │
    ├────────┤     ├────────┤     ├────────┤
    │Flask   │     │Flask   │     │Flask   │
    │Server  │     │Server  │     │Server  │
    │(app.py)│     │(app.py)│     │(app.py)│
    └────────┘     └────────┘     └────────┘
        ▼               ▼               ▼
    ┌──────────────────────────────────────────────┐
    │     Shared Model Storage                     │
    │  • models/startup_model.pkl                  │
    │  • models/preprocessing_info.pkl             │
    │  • (AWS S3 or NFS Mount)                     │
    └──────────────────────────────────────────────┘
            ▼
    ┌──────────────────────────┐
    │   Database (Optional)    │
    │   Prediction History     │
    │   User Data              │
    │   Analytics              │
    └──────────────────────────┘
```

---

**Note:** Save this architecture document for reference during maintenance and scaling.
