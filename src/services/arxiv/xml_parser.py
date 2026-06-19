import logging
import xml.etree.ElementTree as ET
from typing import List, Optional

from src.exceptions import ArxivParseError
from src.schemas.arxiv.researchpaper import ArxivResearchPaper

logger = logging.getLogger(__name__)

class ArxivXmlParser:
    """
    Parses arXiv Atom XML responses into ArxivResearchPaper objects.
    """

    def __init__(self, namespaces: dict):
        self._namespaces = namespaces

    def parse(self, xml_data: str) -> List[ArxivResearchPaper]:
        """
        Parse a full arXiv XML response into a list of papers.
        """
        try:
            root = ET.fromstring(xml_data)
            entries = root.findall("atom:entry", self._namespaces)

            papers = []
            for entry in entries:
                paper = self._parse_entry(entry)
                if paper:
                    papers.append(paper)

            return papers

        except ET.ParseError as e:
            logger.error(f"Malformed XML from arXiv: {e}")
            raise ArxivParseError(f"Failed to parse arXiv XML: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error parsing arXiv response: {e}")
            raise ArxivParseError(f"Unexpected error parsing arXiv response: {e}") from e

    def _parse_entry(self, entry: ET.Element) -> Optional[ArxivResearchPaper]:
        """
        Parse one <entry> element into an ArxivPaper object.
        """
        try:
            arxiv_id = self._get_id(entry)
            if not arxiv_id:
                logger.warning("Skipping entry with no arXiv ID")
                return None
            
            title = self._get_text(entry, "atom:title", clean_newlines=True)
            summary = self._get_text(entry, "atom:summary", clean_newlines=True)
            categories = self._get_categories(entry)
            published_on = self._get_text(entry, "atom:published")
            authors = self._get_authors(entry)
            pdf_url = self._get_pdf_url(entry)

            return ArxivResearchPaper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                summary=summary,
                published_date=published_on,
                categories=categories,
                pdf_url=pdf_url,
            )

        except Exception as e:
            logger.exception(f"Failed to parse XML entry")
            return None

    def _get_text(
        self,
        element: ET.Element,
        path: str,
        clean_newlines: bool = False,
    ) -> str:
        """
        Safely extract text from an XML element.
        """
        xml_element = element.find(path, self._namespaces)

        if xml_element is None or xml_element.text is None:
            return ""

        text = xml_element.text.strip()
        return text.replace("\n", " ") if clean_newlines else text

    def _get_id(self, entry: ET.Element) -> Optional[str]:
        """
        Extract the arXiv paper ID from an entry.
        """
        id_xml_element = entry.find("atom:id", self._namespaces)

        if id_xml_element is None or id_xml_element.text is None:
            return None

        return id_xml_element.text.split("/")[-1]

    def _get_authors(self, entry: ET.Element) -> List[str]:
        """
        Extract all author names from an entry.
        """
        authors = []
        for author in entry.findall("atom:author", self._namespaces):
            name = self._get_text(author, "atom:name")
            if name:
                authors.append(name)
        return authors

    def _get_categories(self, entry: ET.Element) -> List[str]:
        """
        Extract all category tags from an entry.
        """
        categories = []
        for category in entry.findall("atom:category", self._namespaces):
            term = category.get("term")
            if term:
                categories.append(term)
        return categories

    def _get_pdf_url(self, entry: ET.Element) -> str:
        """
        Extract the PDF download URL from an entry.
        """
        for link in entry.findall("atom:link", self._namespaces):
            if link.get("type") == "application/pdf":
                url = link.get("href", "")

                if url.startswith("http://arxiv.org/"):
                    url = url.replace("http://arxiv.org/", "https://arxiv.org/")

                return url

        return ""