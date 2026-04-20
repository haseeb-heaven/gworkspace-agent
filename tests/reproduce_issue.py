import re


def extract_data(body):
    # Fixed regex for Amount Due to handle currency symbols and commas correctly
    # Example: "Your Airtel Postpaid Bill: ₹ 529.82" or "Amount Due: $1,234.56"

    # Let's try to find Bank Name
    # From: statement@emiratesnbd.com -> Emirates NBD
    # From: hello@liv.me -> Liv
    # From: Estatement@emiratesislamic.ae -> Emirates Islamic
    # From: ebill@airtel.com -> Airtel

    bank = "Unknown Bank"
    if "emiratesnbd" in body.lower():
        bank = "Emirates NBD"
    elif "liv.me" in body.lower():
        bank = "Liv"
    elif "emiratesislamic" in body.lower():
        bank = "Emirates Islamic"
    elif "airtel" in body.lower():
        bank = "Airtel"

    # Date extraction
    # "Due by 13-Apr-2026"
    # "Date: 13 Apr 2026"
    date_match = re.search(r'(?:Due by|Date)[:\s]+(\d{1,2}[-\s][A-Za-z]{3}[-\s]\d{4})', body, re.I)
    date = date_match.group(1) if date_match else "Unknown Date"

    # Amount Due extraction - look for currency symbols or keywords
    # AED 1,234.56, ₹ 529.82, $ 10.00
    amount_match = re.search(r'(?:Bill|Due|Total|₹|AED|[\$£€])[:\s]*(?:[^\d\n\r]*)\s*([\d,]+\.\d{2})', body, re.I)
    amount = amount_match.group(1) if amount_match else "Unknown Amount"

    return [bank, date, amount]

# Test cases from previous run
bodies = [
    "From: ebill@airtel.com\nSubject: Your Airtel Postpaid Bill: ₹ 529.82 | Due by 13-Apr-2026",
    "From: statement@emiratesnbd.com\nSubject: Liv E-Statement for SAVINGS ACCOUNT account ending with 6301\nDate: 13 Apr 2026 10:37:31 +0400\nTotal Amount Due: AED 150.00",
    "From: Estatement@emiratesislamic.ae\nSubject: Statement of your Emirates Islamic Credit Card\nDate: 11 Apr 2026 16:21:53 +0400\nMinimum Amount Due: AED 250.00"
]

for b in bodies:
    print(f"Body: {b[:100]}...")
    print(f"Extracted: {extract_data(b)}")
    print("-" * 20)
