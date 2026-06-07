# xml_parser.py
#
# PURPOSE: Parse arXiv's XML API responses into ArxivPaper objects.

import logging
import xml.etree.ElementTree as ET
from typing import List, Optional

from src.exceptions import ArxivParseError
from src.schemas.arxiv.paper import ArxivPaper

logger = logging.getLogger(__name__)


class ArxivXmlParser:
    """
    Parses arXiv Atom XML responses into ArxivPaper objects.

    arXiv returns results as an Atom feed (a type of XML).
    This class knows how to read that format and turn it
    into clean Python objects.

    Usage:
        parser = ArxivXmlParser(namespaces=settings.namespaces)
        papers = parser.parse(xml_data)
    """

    def __init__(self, namespaces: dict):
        """
        Args:
            namespaces: XML namespace mappings needed to read
                        arXiv's Atom format. Comes from settings.
                        Example: {"atom": "http://www.w3.org/2005/Atom"}
        """
        self._namespaces = namespaces

    def parse(self, xml_data: str) -> List[ArxivPaper]:
        """
        Parse a full arXiv XML response into a list of papers.

        Skips individual entries that fail to parse — one bad
        entry won't stop the rest from being processed.

        Args:
            xml_data: Raw XML string from arXiv API

        Returns:
            List of successfully parsed ArxivPaper objects

        Raises:
            ArxivParseError: if the XML itself is malformed
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

    def _parse_entry(self, entry: ET.Element) -> Optional[ArxivPaper]:
        """
        Parse one <entry> element into an ArxivPaper object.

        Returns None instead of raising if parsing fails —
        so one bad paper doesn't crash the whole batch.

        Args:
            entry: One <entry> XML element

        Returns:
            ArxivPaper object, or None if parsing fails
        """
        try:
            arxiv_id = self._get_id(entry)
            if not arxiv_id:
                logger.warning("Skipping entry with no arXiv ID")
                return None

            return ArxivPaper(
                arxiv_id=arxiv_id,
                title=self._get_text(entry, "atom:title", clean_newlines=True),
                authors=self._get_authors(entry),
                abstract=self._get_text(entry, "atom:summary", clean_newlines=True),
                published_date=self._get_text(entry, "atom:published"),
                categories=self._get_categories(entry),
                pdf_url=self._get_pdf_url(entry),
            )

        except Exception as e:
            logger.error(f"Failed to parse entry: {e}")
            return None

    def _get_text(
        self,
        element: ET.Element,
        path: str,
        clean_newlines: bool = False,
    ) -> str:
        """
        Safely extract text from an XML element.

        Args:
            element:        Parent XML element to search inside
            path:           XPath to the element (e.g. "atom:title")
            clean_newlines: If True, replace newlines with spaces

        Returns:
            Text content, or "" if element doesn't exist
        """
        elem = element.find(path, self._namespaces)

        if elem is None or elem.text is None:
            return ""

        text = elem.text.strip()
        return text.replace("\n", " ") if clean_newlines else text

    def _get_id(self, entry: ET.Element) -> Optional[str]:
        """
        Extract the arXiv paper ID from an entry.

        Raw XML value: "https://arxiv.org/abs/2507.17748v1"
        Returns:       "2507.17748v1"

        Args:
            entry: XML entry element

        Returns:
            arXiv ID string, or None if not found
        """
        id_elem = entry.find("atom:id", self._namespaces)

        if id_elem is None or id_elem.text is None:
            return None

        return id_elem.text.split("/")[-1]

    def _get_authors(self, entry: ET.Element) -> List[str]:
        """
        Extract all author names from an entry.

        Raw XML:
            <author><name>Yann LeCun</name></author>
            <author><name>Geoffrey Hinton</name></author>
        Returns:
            ["Yann LeCun", "Geoffrey Hinton"]

        Args:
            entry: XML entry element

        Returns:
            List of author name strings, or [] if none found
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

        Raw XML:
            <category term="cs.AI"/>
            <category term="cs.LG"/>
        Returns:
            ["cs.AI", "cs.LG"]

        Args:
            entry: XML entry element

        Returns:
            List of category strings, or [] if none found
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

        Finds the link with type="application/pdf" and
        upgrades HTTP to HTTPS if needed.

        Args:
            entry: XML entry element

        Returns:
            HTTPS PDF URL, or "" if no PDF link found
        """
        for link in entry.findall("atom:link", self._namespaces):
            if link.get("type") == "application/pdf":
                url = link.get("href", "")

                if url.startswith("http://arxiv.org/"):
                    url = url.replace("http://arxiv.org/", "https://arxiv.org/")

                return url

        return ""