"""Double-entry journal proposals.

PLACEHOLDER package.

Every resolved break produces a *proposed* accounting entry, never a direct
posting. The proposal carries its rationale, and a human approves it unless
policy allows auto-posting (autonomy level 3+).

The keystone of the design is the **Gateway Clearing** account:

    Order captured:   Dr Gateway Clearing    1,200.00
                        Cr Revenue                      1,200.00

    Payout settles:   Dr Bank               58,407.00
      (50 x 1,200)    Dr Processing Fees     1,350.00
                      Dr Processing Fee Tax    243.00
                        Cr Gateway Clearing            60,000.00

Three debit legs, not two: at 200 bps + 3.00 per transaction with 1800 bps GST
levied on the fee, a fifty-transaction batch of 1,200.00 orders deducts 1,350.00
of fees and 243.00 of tax, so 58,407.00 arrives. The tax gets its own account
(``5110``) because input tax credit is reclaimable and the fee is not; folding
them together loses information the business needs.

This yields a self-proving control: the Gateway Clearing balance at period end
must equal the sum of captured-but-unsettled transactions. Any divergence *is*
an unreconciled break -- detected by the ledger itself, independent of the
matching engine. Two independent mechanisms agreeing is much stronger evidence
than either one alone.
"""
