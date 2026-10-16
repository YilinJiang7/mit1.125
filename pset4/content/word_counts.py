"""Count draft body words and spoken narration consistently with review."""
import re

def word_count(body,kind):
    body=body.split('\n## Sources',1)[0]
    if kind=='script':
        body=' '.join(re.findall(r'\*\*Narration\s*:?\*\*\s*:?\s*(.*?)(?=\*\*(?:On screen|Sources)\s*:?\*\*|\n#{1,3} |\Z)',body,re.S|re.I))
    return len(re.findall(r"\b[\w'-]+\b",re.sub(r'\[\d{2}-c\d+\]','',body)))
