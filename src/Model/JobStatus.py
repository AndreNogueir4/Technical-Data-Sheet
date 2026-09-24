from enum import StrEnum


class JobStatus(StrEnum):
    TODO = 'todo'
    IN_PROGRESS = 'in_progress'
    DONE = 'done'
    INVALID = 'invalid'
    ERROR = 'error'
