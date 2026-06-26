import json
import logging
import re
from typing import Dict, List, Optional, Union
from src.schemas.chunking.model import DocumentChunk, ChunkMetadata
from src.config import Settings

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Service for chunking text into overlapping segments.

    Uses word-based chunking with configurable chunk size and overlap.
    Default: 600 words per chunk with 100 word overlap.
    """

    def __init__(self, settings: Settings):
        self.chunk_size = settings.chunking.chunk_size
        self.overlap_size = settings.chunking.overlap_size
        self.min_chunk_size = settings.chunking.min_chunk_size

    def _reconstruct_text(self, words: List[str]) -> str:
        """Reconstruct text from words"""
        return " ".join(words)
    
    def chunk_paper(
        self,
        title: str,
        abstract: str,
        full_text: str,
        arxiv_id: str,
        paper_id: str,
        sections: Optional[Union[Dict[str, str], str, list]] = None,
    ) -> List[DocumentChunk]:
        """Chunk a paper using hybrid section-based approach.

        Strategy:
        - For sections 100-800 words: Use as single chunk with title+abstract
        - For sections <100 words: Combine with adjacent sections
        - For sections >800 words: Split using traditional word-based chunking
        - Fallback to traditional chunking if no sections available
        """
        # Try section-based chunking first
        if sections:
            try:
                section_chunks = self._chunk_by_sections(title, abstract, arxiv_id, paper_id, sections)
                if section_chunks:
                    logger.info(f"Created {len(section_chunks)} section-based chunks for {arxiv_id}")
                    return section_chunks
            except Exception as e:
                logger.warning(f"Section-based chunking failed for {arxiv_id}: {e}")

        # Fallback to traditional word-based chunking
        logger.info(f"Using traditional word-based chunking for {arxiv_id}")
        return self.chunk_text(full_text, arxiv_id, paper_id)

    def chunk_text(
        self, 
        text: str, 
        arxiv_id: str, 
        paper_id: str
    ) -> List[DocumentChunk]:
        """Chunk text into overlapping word-based overlapping segments."""
        if not text or not text.strip():
            logger.warning(f"Empty text provided for paper {arxiv_id}")
            return []

        words = re.findall(r"\S+", text)

        if len(words) < self.min_chunk_size:
            logger.warning(
                f"Text for paper {arxiv_id} has only {len(words)} words, "
                f"less than minimum {self.min_chunk_size}"
            )
            return [self._build_chunk(words, chunk_index=0, arxiv_id=arxiv_id, paper_id=paper_id)]

        step = self.chunk_size - self.overlap_size
        starts = range(0, len(words), step)

        chunks = [
            self._build_chunk(
                words=words,
                chunk_index=i,
                arxiv_id=arxiv_id,
                paper_id=paper_id,
                chunk_start=start,
                chunk_end=min(start + self.chunk_size, len(words)),
            )
            for i, start in enumerate(starts)
            if start < len(words)
        ]

        logger.info(f"Chunked paper {arxiv_id}: {len(words)} words -> {len(chunks)} chunks")
        return chunks

    def _build_chunk(
        self,
        words: List[str],
        chunk_index: int,
        arxiv_id: str,
        paper_id: str,
        chunk_start: int = 0,
        chunk_end: Optional[int] = None,
    ) -> DocumentChunk:
        """Build a single TextChunk from a word list slice."""
        if chunk_end is None:
            chunk_end = len(words)

        chunk_words = words[chunk_start:chunk_end]

        # +1 accounts for the space separator after the preceding words
        start_char = len(" ".join(words[:chunk_start])) + 1 if chunk_start > 0 else 0
        end_char = len(" ".join(words[:chunk_end]))

        return DocumentChunk(
            text=self._reconstruct_text(chunk_words),
            metadata=ChunkMetadata(
                chunk_index=chunk_index,
                start_char=start_char,
                end_char=end_char,
                word_count=len(chunk_words),
                overlap_with_previous=min(self.overlap_size, chunk_start) if chunk_start > 0 else 0,
                overlap_with_next=self.overlap_size if chunk_end < len(words) else 0,
                section_title=None,
            ),
            arxiv_id=arxiv_id,
            paper_id=paper_id,
        )

    def _parse_sections(
        self, 
        sections: Union[Dict[str, str], str, list]
    ) -> Dict[str, str]:
        """Parse sections data into a dictionary."""
        if isinstance(sections, dict):
            return sections
        
        if isinstance(sections, str):
            try:
                sections = json.loads(sections)
            except json.JSONDecodeError:
                logger.warning("Failed to parse sections JSON")
                return {}
        
        if isinstance(sections, list):
            return self._list_to_sections_dict(sections)
        
        return {}

    def _list_to_sections_dict(self, sections: list) -> Dict[str, str]:
        """Convert a list of sections to a title->content dictionary."""
        result = {}
        for i, section in enumerate(sections):
            if isinstance(section, dict):
                title = section.get("title") or section.get("heading") or f"Section {i + 1}"
                content = section.get("content") or section.get("text") or ""
            else:
                title = f"Section {i + 1}"
                content = str(section)
            result[title] = content
            
        return result

    def _chunk_by_sections(
        self, title: str, abstract: str, arxiv_id: str, paper_id: str, sections: Union[Dict[str, str], str, list]
    ) -> List[DocumentChunk]:
        """Implement hybrid section-based chunking strategy.
        """
        # Parse sections data
        sections_dict = self._parse_sections(sections)
        if not sections_dict:
            return []

        # Filter and clean sections
        sections_dict = self._filter_sections(sections_dict, abstract)
        if not sections_dict:
            logger.warning(f"No meaningful sections found after filtering for {arxiv_id}")
            return []

        # Create header (title + abstract)
        header = f"{title}\n\nAbstract: {abstract}\n\n"

        # Process sections using hybrid strategy
        chunks = []
        small_sections = []  # Buffer for combining small sections

        section_items = list(sections_dict.items())

        for i, (section_title, section_content) in enumerate(section_items):
            content_str = str(section_content) if section_content else ""
            section_words = len(content_str.split())

            if section_words < 100:
                # Collect small sections to combine later
                small_sections.append((section_title, content_str, section_words))

                # If this is the last section or next section is large, process accumulated small sections
                if i == len(section_items) - 1 or len(str(section_items[i + 1][1]).split()) >= 100:
                    chunks.extend(self._create_combined_chunk(header, small_sections, chunks, arxiv_id, paper_id))
                    small_sections = []

            elif 100 <= section_words <= 800:
                # Perfect size - create single chunk
                chunk_text = f"{header}Section: {section_title}\n\n{content_str}"
                chunk = self._create_section_chunk(chunk_text, section_title, len(chunks), arxiv_id, paper_id)
                chunks.append(chunk)

            else:
                # Large section - split using traditional chunking
                section_text = f"Section: {section_title}\n\n{content_str}"
                full_section_text = f"{header}{section_text}"

                # Use traditional chunking but with section context
                section_chunks = self._split_large_section(
                    full_section_text, header, section_title, len(chunks), arxiv_id, paper_id
                )
                chunks.extend(section_chunks)

        return chunks

    def _filter_sections(self, sections_dict: Dict[str, str], abstract: str) -> Dict[str, str]:
        """Filter out unwanted sections and avoid duplication.
        """
        filtered = {}
        abstract_words = set(abstract.lower().split())

        for section_title, section_content in sections_dict.items():
            content_str = str(section_content).strip()

            # Skip empty sections
            if not content_str:
                continue

            # Skip metadata/header sections based on title
            if self._is_metadata_section(section_title):
                continue

            # Skip sections that are duplicates of the abstract
            if self._is_duplicate_abstract(content_str, abstract, abstract_words):
                logger.debug(f"Skipping duplicate abstract section: {section_title}")
                continue

            # Skip sections that are too small and contain only metadata
            if len(content_str.split()) < 20 and self._is_metadata_content(content_str):
                logger.debug(f"Skipping metadata section: {section_title}")
                continue

            filtered[section_title] = content_str

        return filtered

    def _is_metadata_section(self, section_title: str) -> bool:
        """Check if a section title indicates metadata/header content."""
        title_lower = section_title.lower().strip()

        metadata_indicators = [
            "content",
            "header",
            "authors",
            "author",
            "affiliation",
            "email",
            "arxiv",
            "preprint",
            "submitted",
            "received",
            "accepted",
        ]

        # Exact matches or very short titles that are likely metadata
        if title_lower in metadata_indicators or len(title_lower) < 5:
            return True

        # Check if title contains only metadata indicators
        for indicator in metadata_indicators:
            if indicator in title_lower and len(title_lower) < 20:
                return True

        return False

    def _is_duplicate_abstract(self, content: str, abstract: str, abstract_words: set) -> bool:
        """Check if section content is a duplicate of the abstract."""
        content_lower = content.lower().strip()
        abstract_lower = abstract.lower().strip()

        # Direct string match (allowing for minor formatting differences)
        if abstract_lower in content_lower or content_lower in abstract_lower:
            return True

        # Word overlap check - if >80% of words overlap, likely duplicate
        content_words = set(content_lower.split())

        if len(abstract_words) > 10:  # Only check for substantial abstracts
            overlap = len(abstract_words.intersection(content_words))
            overlap_ratio = overlap / len(abstract_words)

            if overlap_ratio > 0.8:
                return True

        return False

    def _is_metadata_content(self, content: str) -> bool:
        """Check if content contains only metadata (emails, arxiv IDs, etc.)."""
        content_lower = content.lower()

        # Check for common metadata patterns
        metadata_patterns = [
            "@",  # Email addresses
            "arxiv:",  # ArXiv IDs
            "university",
            "institute",
            "department",
            "college",
            "gmail.com",
            "edu",
            "ac.uk",
            "preprint",
        ]

        # If content is mostly metadata patterns
        word_count = len(content.split())
        if word_count < 30:  # Short content
            metadata_word_count = sum(1 for pattern in metadata_patterns if pattern in content_lower)
            if metadata_word_count >= 2:  # Contains multiple metadata indicators
                return True

        return False

    def _create_combined_chunk(
        self, header: str, small_sections: List, existing_chunks: List, arxiv_id: str, paper_id: str
    ) -> List[DocumentChunk]:
        """Create chunks by combining small sections."""
        if not small_sections:
            return []

        # Combine all small sections
        combined_content = []
        total_words = 0

        for section_title, content, word_count in small_sections:
            combined_content.append(f"Section: {section_title}\n\n{content}")
            total_words += word_count

        combined_text = f"{header}{'\\n\\n'.join(combined_content)}"

        # If still too small, combine with previous chunk if possible
        if total_words + len(header.split()) < 200 and existing_chunks:
            # Try to merge with previous chunk
            prev_chunk = existing_chunks[-1]
            merged_text = f"{prev_chunk.text}\\n\\n{'\\n\\n'.join(combined_content)}"

            # Update the previous chunk
            existing_chunks[-1] = DocumentChunk(
                text=merged_text,
                metadata=ChunkMetadata(
                    chunk_index=prev_chunk.metadata.chunk_index,
                    start_char=0,
                    end_char=len(merged_text),
                    word_count=len(merged_text.split()),
                    overlap_with_previous=0,
                    overlap_with_next=0,
                    section_title=f"{prev_chunk.metadata.section_title} + Combined",
                ),
                arxiv_id=arxiv_id,
                paper_id=paper_id,
            )
            return []

        # Create new chunk with combined content
        sections_titles = [title for title, _, _ in small_sections]
        combined_title = " + ".join(sections_titles[:3])  # Limit title length
        if len(sections_titles) > 3:
            combined_title += f" + {len(sections_titles) - 3} more"

        chunk = self._create_section_chunk(combined_text, combined_title, len(existing_chunks), arxiv_id, paper_id)
        return [chunk]

    def _create_section_chunk(
        self, chunk_text: str, section_title: str, chunk_index: int, arxiv_id: str, paper_id: str
    ) -> DocumentChunk:
        """Create a single section-based chunk."""
        return DocumentChunk(
            text=chunk_text,
            metadata=ChunkMetadata(
                chunk_index=chunk_index,
                start_char=0,
                end_char=len(chunk_text),
                word_count=len(chunk_text.split()),
                overlap_with_previous=0,
                overlap_with_next=0,
                section_title=section_title,
            ),
            arxiv_id=arxiv_id,
            paper_id=paper_id,
        )

    def _split_large_section(
        self, 
        full_section_text: str, 
        header: str, 
        section_title: str, 
        base_chunk_index: int, 
        arxiv_id: str, 
        paper_id: str
    ) -> List[DocumentChunk]:
        """Split large sections using traditional word-based chunking."""
        # Remove header from section text for chunking, then add back to each chunk
        section_only = full_section_text[len(header) :]

        # Use traditional chunking on section content
        traditional_chunks = self.chunk_text(section_only, arxiv_id, paper_id)

        # Add header to each chunk and update metadata
        enhanced_chunks = []
        for i, chunk in enumerate(traditional_chunks):
            enhanced_text = f"{header}{chunk.text}"

            enhanced_chunk = DocumentChunk(
                text=enhanced_text,
                metadata=ChunkMetadata(
                    chunk_index=base_chunk_index + i,
                    start_char=chunk.metadata.start_char,
                    end_char=chunk.metadata.end_char + len(header),
                    word_count=len(enhanced_text.split()),
                    overlap_with_previous=chunk.metadata.overlap_with_previous,
                    overlap_with_next=chunk.metadata.overlap_with_next,
                    section_title=f"{section_title} (Part {i + 1})",
                ),
                arxiv_id=arxiv_id,
                paper_id=paper_id,
            )
            enhanced_chunks.append(enhanced_chunk)

        return enhanced_chunks
