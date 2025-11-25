"""
Shared utility for generating memorable passwords
Used by Fred and Oscar for user account creation
"""
import random

# Word lists for memorable passwords
ADJECTIVES = [
    'purple', 'golden', 'silver', 'cosmic', 'happy', 'swift', 'brave', 'gentle',
    'bright', 'calm', 'crisp', 'fresh', 'grand', 'keen', 'lucky', 'merry',
    'noble', 'proud', 'quiet', 'royal', 'sunny', 'vivid', 'warm', 'zesty',
    'amber', 'azure', 'coral', 'ivory', 'jade', 'maple', 'olive', 'rustic'
]

NOUNS = [
    'tiger', 'eagle', 'river', 'mountain', 'forest', 'ocean', 'sunset', 'thunder',
    'falcon', 'panda', 'dolphin', 'phoenix', 'dragon', 'maple', 'willow', 'cedar',
    'canyon', 'meadow', 'glacier', 'comet', 'nebula', 'aurora', 'breeze', 'crystal',
    'harbor', 'island', 'valley', 'summit', 'rapids', 'garden', 'castle', 'beacon'
]


def generate_memorable_password():
    """
    Generate a memorable password like "purple-tiger-sunset-42"

    Returns:
        str: A memorable password in the format adjective-noun-adjective-number
    """
    adj1 = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    adj2 = random.choice(ADJECTIVES)
    num = random.randint(10, 99)

    return f"{adj1}-{noun}-{adj2}-{num}"
