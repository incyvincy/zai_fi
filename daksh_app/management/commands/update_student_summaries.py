from django.core.management.base import BaseCommand

from daksh_app.longitudinal import compute_all_student_summaries


class Command(BaseCommand):
    help = 'Compute and persist StudentSummary nodes for all students'

    def handle(self, *args, **options):
        self.stdout.write('Starting student summaries computation...')
        try:
            compute_all_student_summaries()
            self.stdout.write(self.style.SUCCESS('Student summaries updated successfully.'))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Failed to update student summaries: {exc}'))
            raise
