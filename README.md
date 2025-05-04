# PDF Parser

Text extraction tool for client specific PDF documents. Purely written in Python3 with no external dependencies.

Parsing and extracting text from PDF could be treated as 5-steps process, done respectively in the following order -after decompressing the pdf file- :
1. traverse PDF logical tree to find all Page objects - in a way that guarantees the correct ordering-. Then for each Page:
2. Retrieve the Fonts information and ToUnicode Table.
3. Retrieve the contents.
4. Decode the contents.
5. Position the text into their right orders.

# Usages:
```consul
python3 main.py [decompressed_pdf_file_name].txt > [out_file_name].txt
```

# Note:
- The python script extracts text from a document and does not recognize text in images. 

- The implementation here is optimized for parsing pdf with CID fonts ”Type0”,  where fonts are explicitly referenced by the Page object and the ToUnicode tables are embedded within the pdf.

# Helpful Resources:
- [`pdf parsing - understanding pdfs`](https://github.com/Bodoral/pdf_parser/blob/main/docs/pdf%20parsing%20-%20understanding%20pdfs.pdf)
- [PDFReference](https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdfs/pdf_reference_archives/PDFReference.pdf)
- [PDF Explained](https://learning.oreilly.com/library/view/pdf-explained/9781449321581/)
- [PDF Structure](PDFStructure.png)
