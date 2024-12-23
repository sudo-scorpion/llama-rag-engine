class PromptTemplate:
    """
    A class to manage and format prompts for the LLM.

    Provides a structured template for generating prompts, including:
    - System instructions
    - Few-shot examples
    - Context 
    - Question

    Attributes:
        SYSTEM_PROMPT (str): System instructions for the LLM.
        FEW_SHOT_EXAMPLES (list): List of few-shot examples.
    """

    SYSTEM_PROMPT = """
    You are a highly informative and comprehensive AI assistant. 
    Given the following context, answer the question accurately and concisely. 
    Cite specific portions of the context to support your answer whenever possible. 
    If the answer cannot be found within the provided context, state so explicitly.
    """

    FEW_SHOT_EXAMPLES = [
        {
            "context": "The Earth revolves around the Sun.",
            "question": "What is the primary celestial body that the Earth revolves around?",
            "answer": "According to the context, the Earth revolves around the Sun." 
        },
        {
            "context": "Water is a compound composed of two hydrogen atoms and one oxygen atom.",
            "question": "What are the components of water?",
            "answer": "The context states that water is composed of two hydrogen atoms and one oxygen atom."
        }
    ]

    @staticmethod
    def format_prompt(context: str, question: str) -> str:
        """
        Formats the prompt by combining system instructions, few-shot examples, 
        context, and the question.

        Args:
            context (str): The context for the question.
            question (str): The question to be answered.

        Returns:
            str: The formatted prompt.
        """

        few_shot_examples = "\n\n".join([
            f"**Context:** {ex['context']}\n"
            f"**Question:** {ex['question']}\n"
            f"**Answer:** {ex['answer']}"
            for ex in PromptTemplate.FEW_SHOT_EXAMPLES
        ])

        prompt = f"{PromptTemplate.SYSTEM_PROMPT}\n\n" \
                 f"{few_shot_examples}\n\n" \
                 f"**Context:** {context}\n\n" \
                 f"**Question:** {question}\n\n" \
                 "**Answer:**"

        return prompt