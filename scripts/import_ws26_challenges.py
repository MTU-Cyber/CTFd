"""One-time import of the WS26 web and forensics challenges."""

from pathlib import Path

from werkzeug.datastructures import FileStorage

from CTFd import create_app
from CTFd.models import Challenges, Flags, db
from CTFd.plugins.dynamic_challenges import DynamicChallenge, DynamicValueChallenge
from CTFd.utils.uploads import upload_file


def import_challenges():
    instancer = "https://instances.cyberctfhub.ie/challenges"
    fileserver = "https://files.cyberctfhub.ie"

    web = [
        ("Purrfect Gallery", "Welcome to Purrfect Gallery, a cheerful collection of cats hiding one carefully guarded secret.", "CTFHub{smuggl1ng_kitties_2ad9687a009fe336}", "India", "http://purrfectgallery.cyberctfhub.ie", None),
        ("Negative Space Art Gallery", "Welcome to Negative Space Art Gallery. Can you afford its most exclusive digital masterpiece?", "CTFHub{c0up0n_st4ck_0v3rfl0w_n3g4t1v3_9x2f_2da9954feff8d698}", "Macao", "http://negativespaceartgallery.cyberctfhub.ie", None),
        ("The Vault", "A high-security digital vault protects a priceless secret. Can you gain access?", "CTFHub{jwt_4lg_n0n3_byp4ss_v4ult_8k3m_d83de3d1aeaa484c}", "Macao", "http://thevault.cyberctfhub.ie", None),
        ("Next in the Middle", "Create an account, share your notes, and uncover the administrator's protected secret.", "CTFHub{93fa8277d2a9a28f}", "Germany", "http://nextinthemiddle.cyberctfhub.ie (web) / nc cyberctfhub.ie 5004 (bot)", None),
        ("Notesboard 1", "A private team notes board contains information that was never meant to be public.", "CTFHub{747f1a0ff756cdf7}", "Germany", f"{instancer}/notesboard", "/challenges/Web-PlayerSources/Notesboard.zip"),
        ("Notesboard 2", "Continue investigating Notesboard and recover its second hidden flag.", "CTFHub{41c16bd8a513c99f}", "Germany", f"{instancer}/notesboard", "/challenges/Web-PlayerSources/Notesboard.zip"),
        ("Yeetus", "Yeetus is a modern writing workspace with customizable preferences and document rendering.", "CTFHub{a_f0rk_1n_the_pr0t0_ch41n_d8de8637f0db68c1}", "Switzerland", f"{instancer}/yeetus", "/challenges/Web-PlayerSources/Yeetus.zip"),
        ("RazorShop", "Browse a premium razor shop and explore its personalized newsletter features.", "CTFHub{r4z0r_sh4rp_t3mpl4t3_1nj3ct10n_dace3423d8f95fbc}", "Germany", f"{instancer}/razorshop", "/challenges/Web-PlayerSources/RazorShop.zip"),
        ("Internal Bank", "Manage two company accounts and find a way to afford the bank's premium digital vault.", "CTFHub{R4c3_0n_7h3_L3dg3r_20a9c25d2243618f}", "Brazil", "http://internalbank.cyberctfhub.ie", None),
        ("Rooster", "Explore a lively online hennery, claim a hen, and uncover its hidden secret.", "CTFHub{W0rld_0f_Ch1cK3n_C0mp371710n5_1e4e838422782f81}", "Brazil", f"{instancer}/rooster", "/challenges/Web-PlayerSources/Rooster.zip"),
    ]

    forensics = [
        ("HID and Seek", "A keyboard should take orders, not give them. This one had other plans.", "flag{sn1ff_th3_k3yb0rd_d41d8cd98f00b204e9800998ecf8427e}", "India", "/challenges/Forensics-HID_and_Seek/challenge.pcap", None),
        ("Under the Radar", "Anomalous outbound traffic and a suspicious host binary were recovered. Identify what was exfiltrated.", "FLAG{dns_with_encryption_yeyeye}", "Chinese Taipei", "/challenges/Forensics-UnderTheRadar/UnderTheRadar.zip", None),
        ("Suspicious Domain", "Investigate unusual DNS activity using the recovered executable and workstation traffic capture.", "WS{Py1nst4ll3r_DN5_3xf1l_4nd_AES_KDF_1s_Fun}", None, "/challenges/Forensics-Chall/challenge2/SuspiciousDomain.zip", None),
        ("PDF Analysis: Painted Over", "A visually redacted publication review may still contain more information than appears on the page.", "WSI{OverlayIsNotRedacted}", None, "/challenges/Forensics-PDF_AnalysisChalls/Task1. Painted Over/publication_review.pdf", None),
        ("PDF Analysis: Out of Order", "An ordinary routing summary contains entries stored in an unexpected order.", "WSI{K7Q2M9V4R8T1N6B3X5Z0}", None, "/challenges/Forensics-PDF_AnalysisChalls/Task2. Out of Order/routing_summary.pdf", None),
        ("PDF Analysis: Margin Notes", "An archived review PDF contains annotation data outside its approved printable area.", "WSI{Cl1pp3dM4rg1n2026XYZ}", None, "/challenges/Forensics-PDF_AnalysisChalls/Task3. Margin Notes/margin_review_packet.pdf", None),
        ("PDF Analysis: Second Reading", "Determine what text the retained indexing profile produces from the supplied recovery document.", "WSI{TwoProfilesOneStream}", None, "/challenges/Forensics-PDF_AnalysisChalls/Task4. Second Reading/recovery_note.pdf", None),
        ("Quiet Update 1", "A suspicious update utility ran shortly before a Windows workstation was captured. Begin with the recovered corporate documents and uncover the first incident record.", "FLAG{N185ZAOOPCJ9G3YG1I6HID14Y}", "Chinese Taipei", None, f"{fileserver}/QuietUpdate.zip"),
        ("Quiet Update 2", "Continue the Quiet Update investigation. Recover the suspicious update utility from memory and locate the delivery record packaged with it.", "FLAG{ASUDE8XXAU1ZVUOT89JU4359B}", "Chinese Taipei", None, f"{fileserver}/QuietUpdate.zip"),
        ("Quiet Update 3", "The recovered update client contains more than its visible code. Examine its packaged program components and reconstruct the protected incident marker.", "FLAG{P4GAUZBFUZ3RLE7HGJ0ZUZRPW}", "Chinese Taipei", None, f"{fileserver}/QuietUpdate.zip"),
        ("Quiet Update 4", "The update client's encrypted configuration is bound to the affected workstation. Recover the host context and decrypt the configuration record.", "FLAG{WC4JLKT4KH9NWQ7HQBS9RU6PE9FB}", "Chinese Taipei", None, f"{fileserver}/QuietUpdate.zip"),
        ("Quiet Update 5", "Complete the investigation by reconstructing the update client's protocol and recovering the final task record left by the collection stage.", "FLAG{65F5MCW0J6UQBK5JK3G2QIPWDL54Y}", "Chinese Taipei", None, f"{fileserver}/QuietUpdate.zip"),
        ("Secure the Web", "Investigate the supplied packet capture and answer all seven questions in `questions.py`. Enter each answer exactly as recovered; the script combines them and prints the flag to submit.", "CTFHub{6898c541a15d3995c0957e3542accad6}", None, "/challenges/Forensics-SecureTheWeb/questions.py", f"{fileserver}/SecureTheWeb.zip"),
        ("Northstar 1: Unpacked Service", "An internal report archive server was isolated after an intrusion. Recover the audit token embedded inside its undocumented packaged service executable.", "flag{6ce8ae578aacf43ebe5dc8356361fa66}", "China", None, f"{fileserver}/NorthstarIntrusion.zip"),
        ("Northstar 2: Poisoned Upload", "Investigators traced the initial compromise to the report upload flow. Among hundreds of routine documents, identify the upload that achieved execution and recover its operator token.", "flag{32152ad72860eb6de0fd47369fbb8705}", "China", None, f"{fileserver}/NorthstarIntrusion.zip"),
        ("Northstar 3: Silent Client", "The successful upload launched a stripped client concealed on the server since deployment. Reverse-engineer the binary and reconstruct the marker it protects.", "flag{68266afc5c9d57da3ef11532000ebe12}", "China", None, f"{fileserver}/NorthstarIntrusion.zip"),
        ("Northstar 4: Wire Session", "The boundary capture recorded the hidden client's exchanges with its controller. Reconstruct the session and recover the marker selected by the operator.", "flag{6df827d0697f4853b6cca0e60ad28d1f}", "China", None, f"{fileserver}/NorthstarIntrusion.zip"),
        ("Northstar 5: Locked Ledger", "The final collection stage left the report database encrypted in place. Recover the remaining key material, restore the ledger, and submit its recorded recovery ticket.", "flag{02760514e1ccecea884c7a09105b867f}", "China", None, f"{fileserver}/NorthstarIntrusion.zip"),
    ]

    for number in range(1, 8):
        old = Challenges.query.filter_by(name=f"Secure the Web {number}").first()
        if old:
            DynamicValueChallenge.delete(old)

    legacy_notesboard = Challenges.query.filter_by(name="Notesboard").first()
    if legacy_notesboard:
        legacy_notesboard.name = "Notesboard 1"
        legacy_notesboard.description = (
            "A private team notes board contains information that was never meant to be public."
            f"\n\n{instancer}/notesboard"
        )
        legacy_flag = Flags.query.filter_by(challenge_id=legacy_notesboard.id).first()
        if legacy_flag:
            legacy_flag.content = "CTFHub{747f1a0ff756cdf7}"
        db.session.commit()
        print("Migrated: Notesboard -> Notesboard 1")

    created = 0
    for name, description, flag, attribution, connection_info, attachment in web:
        if Challenges.query.filter_by(name=name).first():
            print(f"Skipping existing challenge: {name}")
            continue

        challenge = DynamicChallenge(
            name=name,
            description=f"{description}\n\n{connection_info}",
            attribution=attribution,
            connection_info=connection_info,
            category="web",
            type="dynamic",
            state="visible",
            initial=500,
            minimum=100,
            decay=10,
            function="logarithmic",
        )
        db.session.add(challenge)
        db.session.flush()
        db.session.add(Flags(challenge_id=challenge.id, type="static", content=flag, data=""))
        db.session.commit()

        if attachment:
            path = Path(attachment)
            with path.open("rb") as source:
                upload_file(
                    file=FileStorage(source, filename=path.name),
                    type="challenge",
                    challenge_id=challenge.id,
                )
        created += 1
        print(f"Created: {name}")

    for name, description, flag, attribution, local_file, external_url in forensics:
        if external_url:
            description = f"{description}\n\n[Download challenge files]({external_url})"

        existing = Challenges.query.filter_by(name=name).first()
        if existing:
            if name.startswith(("Quiet Update", "Northstar")):
                existing.description = description
                existing.state = "visible"
                db.session.commit()
                print(f"Updated: {name}")
            else:
                print(f"Skipping existing challenge: {name}")
            continue

        challenge = DynamicChallenge(
            name=name,
            description=description,
            attribution=attribution or "",
            connection_info=None,
            category="forensics",
            type="dynamic",
            state="visible",
            initial=500,
            minimum=100,
            decay=10,
            function="logarithmic",
        )
        db.session.add(challenge)
        db.session.flush()
        db.session.add(Flags(challenge_id=challenge.id, type="static", content=flag, data=""))
        db.session.commit()

        if local_file:
            path = Path(local_file)
            with path.open("rb") as source:
                upload_file(
                    file=FileStorage(source, filename=path.name),
                    type="challenge",
                    challenge_id=challenge.id,
                )
        created += 1
        print(f"Created: {name}")

    print(f"Imported {created} challenge(s); all new challenges are public.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        import_challenges()
