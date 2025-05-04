import sys
import argparse
from pdf_parser_classes import PDFDocumentManager

argsp = argparse.ArgumentParser(description='Parse pdf file')
argsp.add_argument('filename', help='path of a decompressed pdf file in .txt format')

if __name__ == "__main__":
    # retrieving file name 
    arg = argsp.parse_args()
    pdf_file_path = arg.filename
    
    with open(pdf_file_path,'r') as in_file:
        pdf_file = in_file.read()
    in_file.close()

    # parsing the file
    parser = PDFDocumentManager(pdf_file)
    parser.parse_document()
    text = parser.text


    print(text)