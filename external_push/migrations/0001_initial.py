# Generated by Django 3.0.14 on 2022-04-07 14:33

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('gravity', '0001_initial'),
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ThingSpeakPushTarget',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Unique name for this push target', max_length=48, unique=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('disabled', 'Disabled'), ('error', 'Error')], default='active', help_text='Status of this push target', max_length=24)),
                ('push_frequency', models.IntegerField(choices=[(59, '1 minute'), (119, '2 minutes'), (299, '5 minutes'), (599, '10 minutes'), (899, '15 minutes'), (1799, '30 minutes'), (3599, '1 hour')], default=900, help_text='How often to push data to the target')),
                ('api_key', models.CharField(default='', help_text='ThingSpeak Channel API Key', max_length=256)),
                ('error_text', models.TextField(blank=True, default='', help_text='The error (if any) encountered on the last push attempt', null=True)),
                ('last_triggered', models.DateTimeField(default=django.utils.timezone.now, help_text='The last time we pushed data to this target')),
                ('brewpi_to_push', models.ForeignKey(blank=True, default=None, help_text="BrewPi Devices to push (ignored if 'all' devices selected)", on_delete=django.db.models.deletion.CASCADE, related_name='thingspeak_push_targets', to='app.BrewPiDevice')),
            ],
            options={
                'verbose_name': 'ThingSpeak Push Target',
                'verbose_name_plural': 'ThingSpeak Push Targets',
            },
        ),
        migrations.CreateModel(
            name='GrainfatherPushTarget',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('active', 'Active'), ('disabled', 'Disabled'), ('error', 'Error')], default='active', help_text='Status of this push target', max_length=24)),
                ('push_frequency', models.IntegerField(choices=[(901, '15 minutes'), (1801, '30 minutes'), (3601, '1 hour')], default=900, help_text='How often to push data to the target')),
                ('logging_url', models.CharField(default='', help_text='Grainfather Logging URL', max_length=256)),
                ('gf_name', models.CharField(default='', help_text='Grainfather brew id (number)', max_length=256)),
                ('error_text', models.TextField(blank=True, default='', help_text='The error (if any) encountered on the last push attempt', null=True)),
                ('last_triggered', models.DateTimeField(default=django.utils.timezone.now, help_text='The last time we pushed data to this target')),
                ('gravity_sensor_to_push', models.ForeignKey(help_text='Gravity Sensor to push (create one push target per sensor to push)', on_delete=django.db.models.deletion.CASCADE, related_name='grainfather_push_target', to='gravity.GravitySensor')),
            ],
            options={
                'verbose_name': 'Grainfather Push Target',
                'verbose_name_plural': 'Grainfather Push Targets',
            },
        ),
        migrations.CreateModel(
            name='GenericPushTarget',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Unique name for this push target', max_length=48, unique=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('disabled', 'Disabled'), ('error', 'Error')], default='active', help_text='Status of this push target', max_length=24)),
                ('push_frequency', models.IntegerField(choices=[(59, '1 minute'), (119, '2 minutes'), (299, '5 minutes'), (599, '10 minutes'), (899, '15 minutes'), (1799, '30 minutes'), (3599, '1 hour')], default=900, help_text='How often to push data to the target')),
                ('api_key', models.CharField(blank=True, default='', help_text='API key required by the push target (if any)', max_length=256)),
                ('brewpi_push_selection', models.CharField(choices=[('all', 'All Active Sensors/Devices'), ('list', 'Specific Sensors/Devices'), ('none', 'Nothing of this type')], default='all', help_text='How the BrewPi devices to push are selected', max_length=12)),
                ('gravity_push_selection', models.CharField(choices=[('all', 'All Active Sensors/Devices'), ('list', 'Specific Sensors/Devices'), ('none', 'Nothing of this type')], default='all', help_text='How the gravity sensors to push are selected', max_length=12)),
                ('target_type', models.CharField(choices=[('http (post)', 'HTTP/HTTPS'), ('tcp', 'TCP (Telnet/Socket)')], default='http (post)', help_text='Protocol to use to connect to the push target', max_length=24)),
                ('target_host', models.CharField(blank=True, default='http://127.0.0.1/', help_text='The URL to push to (for HTTP/HTTPS) or hostname/IP address (for TCP)', max_length=256)),
                ('target_port', models.IntegerField(default=80, help_text='The port to use (not used for HTTP/HTTPS)', validators=[django.core.validators.MinValueValidator(10, 'Port must be 10 or higher'), django.core.validators.MaxValueValidator(65535, 'Port must be 65535 or lower')])),
                ('data_format', models.CharField(choices=[('generic', 'All Data (Generic)')], default='generic', help_text='The data format to send to the push target', max_length=24)),
                ('error_text', models.TextField(blank=True, default='', help_text='The error (if any) encountered on the last push attempt', null=True)),
                ('last_triggered', models.DateTimeField(default=django.utils.timezone.now, help_text='The last time we pushed data to this target')),
                ('brewpi_to_push', models.ManyToManyField(blank=True, default=None, help_text="BrewPi Devices to push (ignored if 'all' devices selected)", related_name='push_targets', to='app.BrewPiDevice')),
                ('gravity_sensors_to_push', models.ManyToManyField(blank=True, default=None, help_text="Gravity Sensors to push (ignored if 'all' sensors selected)", related_name='push_targets', to='gravity.GravitySensor')),
            ],
            options={
                'verbose_name': 'Generic Push Target',
                'verbose_name_plural': 'Generic Push Targets',
            },
        ),
        migrations.CreateModel(
            name='BrewfatherPushTarget',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('active', 'Active'), ('disabled', 'Disabled'), ('error', 'Error')], default='active', help_text='Status of this push target', max_length=24)),
                ('push_frequency', models.IntegerField(choices=[(901, '15 minutes'), (1801, '30 minutes'), (3601, '1 hour')], default=900, help_text='How often to push data to the target')),
                ('logging_url', models.CharField(default='', help_text='Brewfather Logging URL', max_length=256)),
                ('device_type', models.CharField(choices=[('gravity', 'Gravity sensors'), ('brewpi', 'Brewpi sensors')], default='gravity', help_text='What type of device to send', max_length=24)),
                ('error_text', models.TextField(blank=True, default='', help_text='The error (if any) encountered on the last push attempt', null=True)),
                ('last_triggered', models.DateTimeField(default=django.utils.timezone.now, help_text='The last time we pushed data to this target')),
                ('brewpi_to_push', models.ForeignKey(blank=True, help_text='BrewPi Sensors to push (create one push target per sensor to push)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='brewfather_push_target2', to='app.BrewPiDevice')),
                ('gravity_sensor_to_push', models.ForeignKey(blank=True, help_text='Gravity Sensor to push (create one push target per sensor to push)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='brewfather_push_target', to='gravity.GravitySensor')),
            ],
            options={
                'verbose_name': 'Brewfather Push Target',
                'verbose_name_plural': 'Brewfather Push Targets',
            },
        ),
        migrations.CreateModel(
            name='BrewersFriendPushTarget',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('active', 'Active'), ('disabled', 'Disabled'), ('error', 'Error')], default='active', help_text='Status of this push target', max_length=24)),
                ('push_frequency', models.IntegerField(choices=[(59, '1 minute'), (119, '2 minutes'), (299, '5 minutes'), (599, '10 minutes'), (899, '15 minutes'), (1799, '30 minutes'), (3599, '1 hour')], default=900, help_text='How often to push data to the target')),
                ('api_key', models.CharField(default='', help_text='Brewers Friend API Key', max_length=256)),
                ('error_text', models.TextField(blank=True, default='', help_text='The error (if any) encountered on the last push attempt', null=True)),
                ('last_triggered', models.DateTimeField(default=django.utils.timezone.now, help_text='The last time we pushed data to this target')),
                ('gravity_sensor_to_push', models.ForeignKey(help_text='Gravity Sensor to push (create one push target per sensor to push)', on_delete=django.db.models.deletion.CASCADE, related_name='brewers_friend_push_target', to='gravity.GravitySensor')),
            ],
            options={
                'verbose_name': 'Brewers Friend Push Target',
                'verbose_name_plural': 'Brewers Friend Push Targets',
            },
        ),
    ]
