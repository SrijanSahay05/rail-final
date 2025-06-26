from django.apps import AppConfig


class FeatureTransactionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'feature_transaction'
    verbose_name = 'Transaction Management'
    
    def ready(self):
        # Import signals when the app is ready
        import feature_transaction.models  # This will register the signals
