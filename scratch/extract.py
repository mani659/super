import docx
import io

with io.open('scratch/master_plan_dump.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join([p.text for p in docx.Document('archive/master plan.docx').paragraphs]))
