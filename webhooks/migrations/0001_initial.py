# Generated by Django 3.2.20 on 2025-05-28 07:26

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='GitHubWebhookEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('github_delivery_id', models.CharField(max_length=255, unique=True)),
                ('event_type', models.CharField(max_length=50)),
                ('repository_full_name', models.CharField(max_length=255)),
                ('repository_url', models.URLField()),
                ('payload', models.JSONField()),
                ('status', models.CharField(choices=[('received', 'Received'), ('processing', 'Processing'), ('processed', 'Processed'), ('failed', 'Failed'), ('ignored', 'Ignored')], default='received', max_length=20)),
                ('project_id_affected', models.CharField(blank=True, max_length=255, null=True)),
                ('processing_error', models.TextField(blank=True, null=True)),
                ('processing_attempts', models.IntegerField(default=0)),
                ('last_processing_attempt', models.DateTimeField(blank=True, null=True)),
                ('actions_taken', models.JSONField(default=list)),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'db_table': 'github_webhook_events',
                'ordering': ['-received_at'],
            },
        ),
        migrations.CreateModel(
            name='WebhookDeliveryLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('github', 'GitHub'), ('paypal', 'PayPal')], max_length=20)),
                ('webhook_id', models.CharField(max_length=255)),
                ('endpoint_url', models.URLField()),
                ('http_method', models.CharField(default='POST', max_length=10)),
                ('headers', models.JSONField(default=dict)),
                ('payload', models.JSONField()),
                ('response_status_code', models.IntegerField(blank=True, null=True)),
                ('response_headers', models.JSONField(default=dict)),
                ('response_body', models.TextField(blank=True, null=True)),
                ('request_timestamp', models.DateTimeField()),
                ('response_timestamp', models.DateTimeField(blank=True, null=True)),
                ('processing_duration_ms', models.IntegerField(blank=True, null=True)),
                ('delivery_status', models.CharField(choices=[('pending', 'Pending'), ('delivered', 'Delivered'), ('failed', 'Failed'), ('timeout', 'Timeout')], default='pending', max_length=20)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('retry_count', models.IntegerField(default=0)),
                ('max_retries', models.IntegerField(default=3)),
                ('next_retry_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'webhook_delivery_logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WebhookSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_name', models.CharField(max_length=50)),
                ('webhook_url', models.URLField()),
                ('secret_token', models.CharField(blank=True, max_length=255, null=True)),
                ('event_types', models.JSONField(default=list)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('failed', 'Failed'), ('pending', 'Pending')], default='pending', max_length=20)),
                ('external_webhook_id', models.CharField(blank=True, max_length=255, null=True)),
                ('external_subscription_data', models.JSONField(default=dict)),
                ('total_events_received', models.IntegerField(default=0)),
                ('last_event_received_at', models.DateTimeField(blank=True, null=True)),
                ('is_enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'webhook_subscriptions',
                'unique_together': {('service_name', 'webhook_url')},
            },
        ),
        migrations.AddIndex(
            model_name='webhookdeliverylog',
            index=models.Index(fields=['source', 'delivery_status'], name='webhook_del_source_8f7ee1_idx'),
        ),
        migrations.AddIndex(
            model_name='webhookdeliverylog',
            index=models.Index(fields=['webhook_id'], name='webhook_del_webhook_34221e_idx'),
        ),
        migrations.AddIndex(
            model_name='webhookdeliverylog',
            index=models.Index(fields=['created_at'], name='webhook_del_created_3cc125_idx'),
        ),
        migrations.AddIndex(
            model_name='githubwebhookevent',
            index=models.Index(fields=['repository_full_name', 'event_type'], name='github_webh_reposit_802e52_idx'),
        ),
        migrations.AddIndex(
            model_name='githubwebhookevent',
            index=models.Index(fields=['status'], name='github_webh_status_b1769d_idx'),
        ),
        migrations.AddIndex(
            model_name='githubwebhookevent',
            index=models.Index(fields=['received_at'], name='github_webh_receive_bae6aa_idx'),
        ),
    ]
