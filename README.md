# E-Basketball Spread Analyzer

A Python tool for analyzing player matchups and betting spreads in E-Basketball Battle using the BetsAPI service.

## Features
- **Matchup Analysis**: Find betting lines with 80-100% hit rates between two players
- **Form Analysis**: Track recent performance trends over different time periods
- **Head-to-Head Stats**: Win/loss records and average point margins
- **Color-coded Output**: Visual indicators for high-confidence betting lines

## Prerequisites
- Python 3.8+
- BetsAPI account and API token (get one at [BetsAPI.com](https://betsapi.com))

## Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/ebasketball-analyzer.git
cd ebasketball-analyzer

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Get your API token from BetsAPI
2. Replace the `API_TOKEN` in `spreads.py` with your token:
```python
API_TOKEN = "your-api-token-here"
```

## Usage

Run the analyzer:
```bash
python spreads.py
```

### Menu Options:
1. **Analyze Matchup** - Get spread analysis and head-to-head stats
2. **Analyze Form** - View recent performance trends
3. **Exit**

### Example:
```
Select an option (1-3): 1
Enter first player name: bazuka
Enter second player name: lucashin
How many games do you want to analyze? 50
```

## Available Players
- bazuka, lucashin, jovke, kadzima, dzmn, pakapaka
- tapachan, lalkoff, lucker, dzojo, chiefkeef, panteraxball
- andrik, shooter, elel, ugren

## Output Examples

**80-100% Hit Rate Lines:**
- Spread -5.5 | Hit Rate 95.00% (19/20)
- Spread -3.5 | Hit Rate 100.00% [100% GREEN] (20/20)

**Form Analysis:**
```
Last 10 games:
  bazuka: 7/10 wins (70.0%)
  lucashin: 3/10 wins (30.0%)
```

## ⚠️ Disclaimer
This tool is for educational and analytical purposes only. Always gamble responsibly and be aware of the risks involved in sports betting.

## License
see LICENSE file
