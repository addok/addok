# naive neighborhoods algo


letters = 'abcdefghijklmnopqrstuvwxyz'


def fuzzy(word, max=1):
    # inversions
    neighbors = []
    for i in range(0, len(word) - 1):
        neighbor = list(word)
        neighbor[i], neighbor[i+1] = neighbor[i+1], neighbor[i]
        neighbors.append(''.join(neighbor))
    # insertions
    for letter in letters:
        for i in range(0, len(word) + 1):
            neighbor = list(word)
            neighbor.insert(i, letter)
            neighbors.append(''.join(neighbor))
    # substitutions
    for letter in letters:
        for i in range(0, len(word)):
            neighbor = list(word)
            neighbor[i] = letter
            neighbors.append(''.join(neighbor))
    return neighbors


if __name__ == '__main__':
    print(fuzzy('mot'))
