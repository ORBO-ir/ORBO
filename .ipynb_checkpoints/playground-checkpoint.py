from orbo.history import InstrumentHistory

history = InstrumentHistory(
    inscode=778253364357513,
    count=5,
)

df = history.fetch()

print(df.columns)
print(df.head())
