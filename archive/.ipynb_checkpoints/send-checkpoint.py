from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address

node_url = "http://37.27.198.175:9053/"
explorer_url = "https://api.ergoplatform.com/"
appKit = ErgoAppKit(node_url, "mainnet", explorer_url, 'hashcream')
myAddress = "9eg7v2nkypUZbdyvSKSD9kg8FNwrEdTrfC2xdXWXmEpDAFEtYEn"

#collect boxes to spend 1 erg
inputs = appKit.boxesToSpend(address=myAddress,nergToSpend=int(1e9))

#Define output box
outputBox = appKit.buildOutBox(
                value=int(1e9),
                tokens=None,
                registers=None,
                contract=appKit.contractFromAddress(myAddress)
            )

#Build the unsigned transaction
unsignedTx = appKit.buildUnsignedTransaction(
                inputs=inputs,
                outputs=[outputBox],
                fee=int(1e6),
                sendChangeTo=Address.create(myAddress).getErgoAddress()
            )

#Sign the transaction with the node
signedTx = appKit.signTransactionWithNode(unsignedTx)

#Send the transaction
appKit.sendTransaction(signedTx)