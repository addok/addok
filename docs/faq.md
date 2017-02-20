# Frequently Asked Questions (FAQ)

## Can I search on multiple values for a given filter?

For instance: /?type=street&type=housenumber

Addok relies on Redis intersect which only join terms with "AND" and
doesn't know about "OR".

It would be too costly to make multiple passes for each OR term.


## Is the position relevant within the input?

For instance: "33 bd Bordeaux Troyes" vs. "bd de Troyes 33 Bordeaux"

Quick answer: No. Not all countries use the same order for addresses.
Even in one country we can have some subtilities as stated by
the example above.


## Why do I have inconsistent results with abbreviations?

For instance: I'm looking for "BD République" and "Rue République" comes before "Boulevard République" in results.

Addok only resolves abbreviations for searching but never for scoring.
This is because when searching it tries to make its best to guess what the user
is really looking for. At scoring time and by design, we only keep the
original input to be sure that our guesses aren't too magical and far from
the reality.

## How is the score computed?

Score is:

- string distance on a 0-1 range scale
- document importance on a 0-0.1 range scale
- optionally geographical distance on a 0-0.1 range scale
  (if a center has been given)

Then scaled back to a 0-1 range scale.

*Note: the score computation is considered an internal detail and may change
anytime. It's only used for sorting.*
