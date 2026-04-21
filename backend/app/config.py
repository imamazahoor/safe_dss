from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://safe_user:safe_pass@localhost:5432/safe_dss"
    stage1_model_path: str = "../analysis/outputs/sepsis_6_12h/rf_stage1_holdout.joblib"
    stage2_model_path: str = "../analysis/outputs/risk_severity_flagged/rf_stage2_holdout.joblib"
    stage1_high_threshold: float = 0.70
    stage1_moderate_threshold: float = 0.45

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
