import logging
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from users.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create a default superuser with predefined credentials from settings."

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force creation even if superuser already exists (will update existing user).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose logging output.",
        )

    def handle(self, *args, **options):
        """Execute the management command."""
        # Setup logging
        if options['verbose']:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        # Get credentials from settings
        username = "admin"
        email = settings.DEFAULT_ADMIN_EMAIL
        password = settings.DEFAULT_ADMIN_PASSWORD

        logger.info("Creating superuser with username: %s, email: %s", username, email)

        # Check if user already exists
        user_exists = User.objects.filter(username=username).exists()

        if user_exists and not options['force']:
            logger.warning("Superuser with username '%s' already exists. Use --force to update.", username)
            return

        if user_exists and options['force']:
            # Update existing user
            user = User.objects.get(username=username)
            user.email = email
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()
            logger.info("Updated existing superuser: %s", username)
        else:
            # Create new user
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            logger.info("Created new superuser: %s", username)

        # Verify the user was created/updated correctly
        user.refresh_from_db()
        if user.is_superuser and user.is_staff:
            logger.info("Superuser verification successful")
        else:
            raise CommandError("Failed to create/update superuser with proper permissions")

        logger.info("Superuser creation completed successfully!")