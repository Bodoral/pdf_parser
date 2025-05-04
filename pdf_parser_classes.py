import re
import numpy as np
from binascii import unhexlify, hexlify
from typing import List, Dict,Tuple


class PDFDocumentManager:
    """
    PDFDocumentManager is the main class,it parses and converts PDF file 
    from binary to txt format. A reference to a PDF file is needed.
    
    #Usage:
      parser = PDFDocumentManager(decompressed_pdf_document)
      parser.parse_document()
    """
    
    def __init__(self, pdf_document:str)->None:
        """
        #Args:
        - pdf_document: decompressed pdf document
        """
        self.pdf_document = pdf_document
        # Finds all Page obejcts which are in the following format "obj NUMBER \n Type /Page"
        self.page_objects = re.findall(
            re.compile(r"""obj\s[0-9]+\s0\n\sType:\s/Page[a-zA-Z0-9\n\s:,.<>_/\[\]]+Contents[a-zA-Z0-9\n\s:,.<>_/\[\]]+Font[a-zA-Z0-9\n\s:,.<>_/\[\]]+"""),
            pdf_document)
        self.text = ''
        
    def parse_document(self):
        """
        Parse the entire pdf document.
        """
        entire_pages_text = ''
        for page in self.page_objects:
            pdf_page_manager = PDFPageManager(page,self.pdf_document)
            pdf_content_parser = PDFContentParser(pdf_page_manager)
            pdf_content_parser.parse()

            entire_pages_text += pdf_content_parser.sorted_decoded_text
        self.text = entire_pages_text



class PDFSyntaxError(Exception):
    pass

class PDFPageManager:

    """
    PDFPageManager facilitates reuse of a page shared resources
    such as fonts, cmaps, contents references.
    
    #Usage:
        pdf_page_manager = PDFPageManager(page_object,decompressed_pdf_document)
    """
    
    def __init__(self, page:str, pdf_document:str):
        """
        #Args:
        - page: page object
        - pdf_document: decompressed pdf document
        """
        self.page = page
        self.fonts_mapping_dict = self.get_fonts_mapping_dict(pdf_document)
        self.contents = self.get_content(pdf_document)
        self.cropbox_x,self.cropbox_y = self.get_cropbox()
    
    
    def __get_fonts(self)->Dict:
        """
        Retrieve fonts references used in the page.
        #Returns:
            - Dict containing fonts objects reference numbers
        """
        fonts_ref = {' '.join(font).split()[0]:' '.join(font).split()[1] 
                 for font in re.findall('/([A-Z][1-9]_[0-9])\s([0-9]+)|/([A-Z]+[1-9])\s([0-9]+)',
                                self.page.split("/Font\n")[-1].split('>>')[0])}
        return fonts_ref
    
    
    def __get_cmap(self, font_ref:str,pdf_document:str)->Dict:
        """
        Retrieve ToUnicode table -Type 0- for a given font.
        #Args:
            - font_ref: font object reference 
            - pdf_document: decompressed pdf file
        #Returns:
            - ToUnicode table saved in a dictionary
        """
        # Finding cmap reference associated to a specific font
        cmap_ref = re.findall(re.compile(fr'(obj\s{font_ref}\s0\n[a-zA-Z0-9\n\s:,.<_/\[\]+-]+/ToUnicode\s)([0-9]+)'),pdf_document)[0][1]

        # Traverse to cmap object and retrieve the cmap and save it into a dictionary
        cmap = re.findall(re.compile(fr"""(obj\s{cmap_ref}\s0\n[a-zA-Z0-9\n\s:,.<>_+-/\[\]\\']+)(nbegincmap.*?nendcmap)"""),pdf_document)[0][1]
        cmap_as_list = re.findall(re.compile('<[a-fA-F0-9]+> <[a-fA-F0-9]+>'), cmap)

        return {encode.split()[0].replace('<','').replace('>',''):unhexlify(encode.split()[1].replace('<','').replace('>','')).decode('utf-16-be') 
                          for encode in cmap_as_list}
        
    
    def get_fonts_mapping_dict(self, pdf_document:str)->Dict:
        """
        Retrieve ToUnicode tables for all fonts referenced by the page.
        and save it in a dictionary.
        #Args:
            - pdf_document: decompressed pdf file
        #Returns:
            - Page content as a string. 
            - Nested dictionary in the following format  {font_var_name: {font_encoding: unicode}}.
        """
        fonts_mapping_dict = {}
        fonts_references = self.__get_fonts()
        for font, ref in fonts_references.items():
            fonts_mapping_dict[font] = self.__get_cmap(ref, pdf_document)
        return fonts_mapping_dict

    
    def get_content(self, pdf_document:str)->str:
        """
        Retrive content obejct
        #Args:
            - pdf_document: decompressed pdf file
        #Returns:
            - Page content as a string 
        """
        contents_ref = self.page.split('Contents ')[1].split(' ')[0]
        try:
            content = re.findall(re.compile(fr"""(obj\s{contents_ref}\s0\n[a-zA-Z0-9\n\s:,.<>_+-/\[\]\\()]+)('.*?')"""),pdf_document)[0][1]
        except:
            try:
                content = re.findall(re.compile(fr"""(obj\s{contents_ref}\s0\n[a-zA-Z0-9\n\s:,.<>_+-/\[\]\\()]+)(".*?")"""),pdf_document)[0][1]
            except:
                raise PDFSyntaxError('Content object syntax error '%contents_ref)
                

        return content

    
    def get_cropbox(self)->Tuple[float,float]:
        """
        Get x and y coordinates of the visible region for default user space
        """
        cropbox_x = float(re.findall('[\d+\.\d+]+', self.page.split('/CropBox')[1])[:4][-2])
        cropbox_y = float(re.findall('[\d+\.\d+]+', self.page.split('/CropBox')[1])[:4][-1])
        return cropbox_x,cropbox_y
    

    


class PDFContentParser:
    """
    PDFContentParser used to parse PDF content streams
    that is contained in each page and has instructions
    for rendering the page.
    """
    
    def __init__(self, PdfResourceManager):
        self.PdfResourceManager = PdfResourceManager
        self.Tm = np.array([[1,0,0],  # Initial value -PDF specification- 
                           [0,1,0],
                           [0,0,1]])
        self.Tl = 0                   # Initial value: 0 -PDF specification-
        self.text_with_coordinates = dict()
        self.sorted_decoded_text = ""
        
        
    def get_text_matrices(self, bt:str)->None:
        """
        Get and updated text matrix.             
        #Arg:
            - bt: BT tags or text string "TJ/j tags"

        """

        if 'Tm' in bt:
            Tm_new = bt.split('Tm')[0].split('\\n')[-1]
            a,b,c,d,e,f = list(map(float,Tm_new.split()[-6:]))
            
            self.Tm = np.array([[a,b,0],#     - a: horizontal scale          - b: vertical scale
                                 [c,d,0],#    - c: horizontal rotation       - d: vertical rotation
                                [e,f,1]])#    - e: horizontal position "x"   - f: vertical position "y"
        else:
            pass
        
        
    def get_text_coordinate(self, Tj:str)->None:
        """
        Get corresponding text coordinates and update 
        text matrix "Tm" and text leading "Tl"
        #Arg:
            - Tj: Text string either Tj or TJ
        """
        if 'Td' in Tj:
            for Td in Tj.split(' Td')[:-1]:
                # find x and y 
                Tx = float(Td.split('\\n')[-1].split()[-2])
                Ty = float(Td.split('\\n')[-1].split()[-1])
                Tlm = np.array([[1,0,0],
                                [0,1,0],
                                [Tx,Ty,1]])
                self.Tm =  Tlm.dot(self.Tm)  

        elif 'TD' in Tj:
            for TD in Tj.split(' TD')[:-1]:
                # update text leading
                self.Tl = float(TD.split('\\n')[-1].split()[-1])
                # find x and y 
                Tx = float(TD.split('\\n')[-1].split()[-2])
                Ty = float(TD.split('\\n')[-1].split()[-1])
                Tlm = np.array([[1,0,0],
                                [0,1,0],
                                [Tx,Ty,1]])
                self.Tm = Tlm.dot(self.Tm)

        elif 'T*' in Tj:
            Tx =0 
            Ty = self.Tl
            Tlm = np.array([[1,0,0],
                            [0,1,0],
                            [Tx,Ty,1]])
            self.Tm = Tlm.dot(self.Tm)
            
    def decode_content(self, tag:str,used_font:str)->str:
        """
        #Args:
            - tag: text tags.i.e. <XXXX> inside a Tj/J
            - used_font: The arible name of the font used in the encode the text
        #Return:
            - Decoded text
        """
        fonts_mapping_dic = self.PdfResourceManager.fonts_mapping_dict
        
        decoded_text = ""
        tag = tag.replace("<","")
        tag = tag.replace(">","")
        for i in range(0,len(tag), 4):
            try:
                decoded_text= fonts_mapping_dic[used_font][tag[i:i+4]]+ decoded_text
            except:
                pass
        return decoded_text
    
    
    
        
    def store_text_with_coordinates(self, text:str)->None:
        """
        Store decoded text into a dictionary to position text 
        into its right palce i.e {y:{x:text}}
        #Args:
            - text: decoded text(readable text)
        #Return:
            None, It applys changes directly to the dictionary
        """
        Tx = self.Tm[2][0] #Tx: represent offset in a line
        Ty = self.Tm[2][1] #Ty:represent line
        if (Tx > 0 and Ty > 0):
            Tx = int(Tx)
            Ty = int(Ty)

            y = self.text_with_coordinates.setdefault(Ty,{})
            try:
                y[Tx] = text +y[Tx]
            except:
                x = y.setdefault(Tx,text)
                
                

    def arranging_text(self)->None:
        """
        Sort the dictionary {y:{x:text}} and position text into their right palces and
        save it as a string.
        """
        text = ""

        for line in sorted(self.text_with_coordinates,reverse =True):
            for word in sorted(self.text_with_coordinates[line],reverse =True):
                text += self.text_with_coordinates[line][word]
        self.sorted_decoded_text = text
    
    
    
    def parse(self)->None:
        """
        Parse string streams in the content object.
        """
        content = self.PdfResourceManager.contents
        BTs = content.split("BT")
        used_font = None
        for j in range(1,len(BTs)):
            bt = BTs[j]
            
             # 1- Finding text string in TJ 
            for Tj in bt.split('Tj'):
                if 'TJ' in Tj:
                    for TJ in Tj.split('TJ')[:-1]:
                        try:
                            used_font = re.findall(re.compile(r"""(C2_[0-9]+)\s"""), TJ)[0]
                        except:
                            pass
                        # Update text metrics
                        self.get_text_matrices(TJ)               
                        self.get_text_coordinate(TJ)
                        # Finding text strings
                        text_tags = re.findall("<[0-9a-fA-F]+>", TJ)
                        for text_tag in text_tags:
                            text = self.decode_content(text_tag,used_font)
                            self.store_text_with_coordinates(text)

                # 2- Finding text string in Tj
                Tj_ = Tj.split('TJ')[-1]
                try:
                    used_font = re.findall(re.compile(r"""(C2_[0-9]+)\s"""), Tj_)[0]
                except:
                    pass

                # Get text metrics
                self.get_text_matrices(Tj_)
                self.get_text_coordinate(Tj_)
                # Finding text strings
                text_tags = re.findall("<[0-9a-fA-F]+>", Tj_)
                for text_tag in text_tags:
                    text = self.decode_content(text_tag,used_font)
                    self.store_text_with_coordinates(text)
        self.arranging_text()
