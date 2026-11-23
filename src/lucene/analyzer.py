
"""Shared Lucene analyzer matching the SQLite baseline tokenizer."""



TOKENIZER_PATTERN = r"\b[a-zA-Z]{3,}\b"


def create_analyzer():
    """Create an analyzer matching the SQLite tokenizer.

    Tokenization:
    - ASCII alphabetic tokens only
    - Minimum token length of three characters
    - Lowercase normalization
    - No stemming or stopword removal
    """

    from java.util import HashMap
    from org.apache.lucene.analysis.custom import CustomAnalyzer


    tokenizer_args = HashMap()
    tokenizer_args.put("pattern", TOKENIZER_PATTERN)
    tokenizer_args.put("group", "0")

    filter_args = HashMap()

    return (
        CustomAnalyzer.builder()
        .withTokenizer("pattern", tokenizer_args)
        .addTokenFilter("lowercase", filter_args)
        .build()
    )
