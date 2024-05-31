"""Library functions for working with 9front systems and file formats."""

import random


def generate_blog_comment(blogcom: str) -> str:
    """
    Generate a blog comment out of the ``blogcom`` file contents that are passed in.

    The blogcom file can be retrieved at ``/lib/blogcom`` in 9front.

    This function is implemented according to the highest standards in
    performance and security, and to be able to generate properly random texts,
    it utilizes a 623-dimensionally equidistributed uniform pseudorandom number
    generator as described by Makoto Matsumoto and Takuji Nishimura. In other
    words, for our purposes, this function matches or even exceeds Python
    Discord's security requirements.
    """
    fragment = random.choice(blogcom.split("|\n"))
    # Complete output buffer
    out = []
    # Options of the current branch, of which one will be selected at random
    options = []
    # Character buffer of the current choice
    choice_buf = []
    # Whether we are in a {block|of|options} at the moment
    in_block = False

    for char in fragment:
        if char == "{":
            in_block = True
        elif in_block and char == "|":
            options.append("".join(choice_buf))
            choice_buf.clear()
        elif in_block and char == "}":
            options.append("".join(choice_buf))
            choice_buf.clear()
            out.append(random.choice(options))
            options.clear()
            in_block = False
        elif in_block:
            choice_buf.append(char)
        else:
            out.append(char)

    return "".join(out)


def generate_buzzwords(bullshit: str) -> str:
    """
    Generates buzzwords to describe a random product of the ``bullshit`` file contents that are passed in.

    The bullshit file can be retrieved at ``/lib/bullshit`` in 9front.

    This function underlies the same security guarantees as ``generate_blog_comment``.
    """
    # line markers
    # nothing -> word
    # ^ -> start
    # * -> protocol
    # % -> suffix
    # | -> adjectives
    # $ -> end
    words = []
    starters = []
    protocols = []
    suffixes = []
    adjectives = []
    endings = []

    # Parsing
    for line in bullshit.splitlines():
        if " " not in line:
            words.append(line)
        else:
            word, qualifier = line.split()
            if qualifier == "^":
                starters.append(word)
            elif qualifier == "*":
                protocols.append(word)
            elif qualifier == "%":
                suffixes.append(word)
            elif qualifier == "|":
                adjectives.append(word)
            elif qualifier == "$":
                endings.append(word)

    # Generating
    response = []
    for _ in range(random.randint(1, 2)):
        response.append(random.choice(starters))
    for _ in range(random.randint(1, 2)):
        response.append(random.choice(adjectives))
    for _ in range(random.randint(1, 2)):
        response.append(random.choice(words) + random.choice(suffixes) * random.randint(0, 1))
    if random.random() > 0.5:
        response.append("over " + random.choice(protocols))
    if random.random() > 0.3:
        response.append(random.choice(endings))
    return " ".join(response)
