"""Disposable, resource-limited extraction worker. Reads bytes from stdin; never writes files."""
import io
import json
import sys
import zipfile

MAX_TEXT = 20000

def extract_pdf(raw: bytes):
    from pypdf import PdfReader, filters
    # Limit decompressed stream sizes more aggressively than pypdf's defaults.
    for name in ('ZLIB_MAX_OUTPUT_LENGTH','LZW_MAX_OUTPUT_LENGTH','RUN_LENGTH_MAX_OUTPUT_LENGTH','JBIG2_MAX_OUTPUT_LENGTH','MAX_DECLARED_STREAM_LENGTH'):
        if hasattr(filters,name): setattr(filters,name, 10*1024*1024)
    reader = PdfReader(io.BytesIO(raw), strict=False, root_object_recovery_limit=1000)
    if reader.is_encrypted: return {'error':'Password-protected PDFs are not supported. Upload an unlocked copy.'}
    if len(reader.pages)>12: return {'error':'PDF must contain no more than 12 pages.'}
    pieces=[]
    for page in reader.pages:
        pieces.append(page.extract_text() or '')
        if sum(map(len,pieces))>MAX_TEXT: break
    return {'text':'\n'.join(pieces)}

def extract_docx(raw: bytes):
    from docx import Document
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(infos)>200 or len(set(names))!=len(names) or sum(i.file_size for i in infos)>16*1024*1024:
            return {'error':'DOCX is too complex or too large to process safely.'}
        if 'word/document.xml' not in names or '[Content_Types].xml' not in names or 'word/vbaProject.bin' in names:
            return {'error':'Invalid or unsupported DOCX file.'}
        for i in infos:
            if i.flag_bits & 1 or i.file_size>8*1024*1024 or (i.file_size>100000 and i.file_size/max(i.compress_size,1)>200):
                return {'error':'DOCX is encrypted or too compressed to process safely.'}
            if i.filename.startswith('/') or '..' in i.filename.replace('\\','/').split('/'):
                return {'error':'Invalid DOCX structure.'}
    doc=Document(io.BytesIO(raw))
    parts=[]
    # Include table text as well as ordinary body paragraphs. Reading order of
    # complex layouts, headers, text boxes, images and footers can differ.
    for element in doc.iter_inner_content():
        if hasattr(element,'text'): parts.append(element.text)
        elif hasattr(element,'rows'):
            for row in element.rows:
                parts.append(' | '.join(cell.text for cell in row.cells))
        if sum(map(len,parts))>MAX_TEXT: break
    return {'text':'\n'.join(parts)}

def main():
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (8,9))
            resource.setrlimit(resource.RLIMIT_AS, (384*1024*1024,384*1024*1024))
        except (ImportError, OSError, ValueError):
            pass  # Non-POSIX platforms lack these optional process limits.
        raw=sys.stdin.buffer.read(5*1024*1024+1)
        if len(raw)>5*1024*1024: result={'error':'File must be no larger than 5 MB.'}
        elif len(sys.argv)!=2 or sys.argv[1] not in ('pdf','docx'): result={'error':'Unsupported file type.'}
        else: result=extract_pdf(raw) if sys.argv[1]=='pdf' else extract_docx(raw)
        if 'text' in result:
            text=result['text'].replace('\x00','').strip()
            if len(''.join(text.split()))<50:
                result={'error':'Could not extract enough text. This may be a scanned PDF or image-only document; OCR is not supported. Upload a text-based PDF or DOCX.'}
            else: result={'text':text[:MAX_TEXT], 'truncated':len(text)>MAX_TEXT}
        print(json.dumps(result,ensure_ascii=True))
    except Exception:
        # Do not log document bytes or parser errors that could contain private data.
        print(json.dumps({'error':'Could not safely read this file. Please upload a valid text-based PDF or DOCX.'}))

if __name__=='__main__': main()
