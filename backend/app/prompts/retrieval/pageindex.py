import re
from typing import Dict, Any, List

class PageIndexBuilder:
    """
    Builds structured index hierarchy: Act -> Chapter -> Section
    Extracts act metadata, ensuring queries like 'Section 66 IT Act' resolve directly.
    """
    def __init__(self):
        pass

    def build_tree_from_text(self, text: str) -> Dict[str, Any]:
        # Parse text line by line or section by section and build a dictionary hierarchy
        tree = {"chapters": {}}
        current_chapter = "General"
        current_section = None
        
        chap_pattern = re.compile(r"(?i)^\s*(?:CHAPTER|CHAP\.)\s+([IVXLCDM\d\-\u2013]+)(.*)$")
        sec_pattern = re.compile(r"(?i)^\s*(?:Section|Sec\.)\s*(\d+[A-Z]*)(.*)$")
        
        lines = text.split("\n")
        current_section_lines = []
        
        for line in lines:
            chap_match = chap_pattern.match(line)
            sec_match = sec_pattern.match(line)
            
            if chap_match:
                # Save previous section if exists
                if current_section and current_section_lines:
                    if current_chapter not in tree["chapters"]:
                        tree["chapters"][current_chapter] = {"sections": {}}
                    tree["chapters"][current_chapter]["sections"][current_section] = "\n".join(current_section_lines).strip()
                    current_section_lines = []
                
                chap_num = chap_match.group(1).strip()
                chap_title = chap_match.group(2).strip()
                # Strip leading hyphens, dashes, colons and spaces
                chap_title = re.sub(r'^[\s\-–—:]+', '', chap_title).strip()
                current_chapter = f"Chapter {chap_num}"
                if chap_title:
                    current_chapter += f" - {chap_title}"
                current_section = None
                
            elif sec_match:
                # Save previous section if exists
                if current_section and current_section_lines:
                    if current_chapter not in tree["chapters"]:
                        tree["chapters"][current_chapter] = {"sections": {}}
                    tree["chapters"][current_chapter]["sections"][current_section] = "\n".join(current_section_lines).strip()
                
                current_section = sec_match.group(1).strip()
                # Start new section lines, include the header text
                header_text = sec_match.group(2).strip()
                line_to_add = f"Section {current_section}"
                if header_text:
                    line_to_add += f" {header_text}"
                current_section_lines = [line_to_add]
            else:
                if current_section is not None:
                    current_section_lines.append(line)
                    
        # Save last section
        if current_section and current_section_lines:
            if current_chapter not in tree["chapters"]:
                tree["chapters"][current_chapter] = {"sections": {}}
            tree["chapters"][current_chapter]["sections"][current_section] = "\n".join(current_section_lines).strip()
            
        return tree

    def extract_section_headers(self, text: str) -> List[Dict[str, Any]]:
        # Chunks acts by section headers and tags with section_number
        tree = self.build_tree_from_text(text)
        chunks = []
        for chap_name, chap_data in tree.get("chapters", {}).items():
            for sec_num, sec_text in chap_data.get("sections", {}).items():
                chunks.append({
                    "section": sec_num,
                    "text": sec_text
                })
        return chunks

