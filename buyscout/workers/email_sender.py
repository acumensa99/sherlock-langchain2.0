import os
from email.mime.application import MIMEApplication
from db import db
from models.product import Product
from models.queries import get_winning_and_loosing_asin_count, get_lost_due_to_price_count, \
    get_lost_due_to_rating_count, get_lost_due_to_delivery_speed_count, get_insights_from_excel
from models.storefront import StoreFront
from peewee import fn, Case
from dotenv import load_dotenv
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()
# Your SMTP configuration
SMTP_SERVER = "smtp.zoho.in"
SMTP_PORT = 465
SMTP_USERNAME = "shaishav.m@instadata.works"
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # Use an App Password if you're using Gmail

recipients = {
    "RK World Infocom": [
        "achyutha@rkworldinfocom.com",
        "chethan@rkworldinfocom.com",
        "sanjana@rkworldinfocom.com",
        "raghav@rkworldinfocom.com",
        "mahendra@rkworldinfocom.com",
        "naveen.vyas@rkworldinfocom.com",
        "sripathi@rkworldinfocom.com"
    ],
    "Clicktech Retail": [
        # "vijay.r@clicktechretail.com",
        # "ankit.g@clicktechretail.com",
        "nishit.g@clicktechretail.com",
        # "nishant.c@clicktechretail.com",
        "raghavendra.m@clicktechretail.com",
        "neha.a@clicktechretail.com",
        "sourik.s@newtrendscommerce.in",
        # "sanjay.l@clicktechretail.com"
    ],
    "Kuber Mart Industries Pvt. Ltd.": [
        "robin.vijan@globalbees.com"
    ],
    "Shadow Etail": [
        "santhosh@infinitiventures.in"
    ],
    "HaloHop": [
        "jaysing.kashid@gmail.com"
    ],
    "shilpa-sales": [
        "shalinlunia@gmail.com"
    ],
    "test": [
        "dibyajyoti49@outlook.com"
    ]
}


def send_mail(seller_name, asin_won, asin_lost, due_to_price, due_to_rating, due_to_delivery_speed, EXCEL_FILE_PATH, date):
    # Recipient
    TO_EMAIL = recipients.get(seller_name, [])
    # TO_EMAIL = recipients.get("test", [])

    BCC_EMAIL = [
        # "shaishav.mahaseth@gmail.com",
        # "shaishav.mahaseth@acumensa.co",
        # "k.sameera.n@gmail.com",
        # "praveshsenthil@gmail.com",
        # "dibyajyoti49dey@gmail.com"
        "shaishav.m@instadata.works"
    ]
    FROM_EMAIL = SMTP_USERNAME
    SUBJECT = f"{seller_name} Amazon BuyBox Performance Alert for {date}"

    current_year = datetime.datetime.now().year
    asin_won = round((asin_won / (asin_won + asin_lost)) * 100, 1)
    asin_lost = round(100 - asin_won, 1)
    # Load and format the HTML template
    html_template = f"""
   <html>

<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
</head>

<body>
    <div dir="ltr">
        <h3><span style="font-weight:normal">
                <font size="4" face="times new roman, serif">Hey {seller_name} Team,</font>
            </span></h3>
        <p>
            <font size="4" face="times new roman, serif">We're ready with an Objective Analysis of your Buybox Performance for {date}. Here's what we found*:</font>
        </p>
        <p>
            <font size="4" face="times new roman, serif"><img alt="📊" aria-label="📊" src="https://fonts.gstatic.com/s/e/notoemoji/16.0/1f4ca/72.png" class="gmail-CToWUd" style="height: 1.2em; width: 1.2em; vertical-align: middle;">&nbsp;<strong>Your Buy Box Performance
                    :</strong><br>
            </font>
        </p>
        <p>
            <font size="4" face="times new roman, serif">&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;✅&nbsp;<b>{asin_won}% Win Rate</b>&nbsp;</font>
        </p>
        <p>
            <font size="4" face="times new roman, serif">&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;❌&nbsp;<b>{asin_lost}% Loss Rate</b></font>
        </p>
        <p><img alt="🔎" aria-label="🔎" src="https://fonts.gstatic.com/s/e/notoemoji/16.0/1f50e/72.png" class="gmail-CToWUd" style="font-family: &quot;times new roman&quot;, serif; font-size: large; height: 1.2em; width: 1.2em; vertical-align: middle;"><span style="font-family:&quot;times new roman&quot;,serif;font-size:large">&nbsp;</span><strong style="font-family:&quot;times new roman&quot;,serif;font-size:large">Why
                You Lost&nbsp;</strong><b style="font-family:&quot;times new roman&quot;,serif;font-size:large">BuyBoxes</b><strong style="font-family:&quot;times new roman&quot;,serif;font-size:large">:</strong></p>
        <ul>
            <li style="margin-left:15px">
                <p>
                    <font size="4" face="times new roman, serif"><strong>Price:</strong>&nbsp; {due_to_price} times</font>
                </p>
            </li>
            <li style="margin-left:15px">
                <p>
                    <font size="4" face="times new roman, serif"><strong>Delivery Speed:</strong>&nbsp;{due_to_delivery_speed} times</font>
                </p>
            </li>
            <li style="margin-left:15px">
                <p>
                    <font size="4" face="times new roman, serif"><strong>Seller Rating:</strong>&nbsp;{due_to_rating} times</font>
                </p>
            </li>
        </ul>
        <p><i>
                <font face="times new roman, serif">*Report card generated by measuring across 2 major pincodes, around the time email is sent. More details in the sheet below.</font>
            </i></p>
            <br>
        <p><b>📎📎</b><span style="font-family:&quot;times new roman&quot;,serif;font-size:large"><u>Detailed Report Attached</u></span></p>
        <p>
            <font size="4" face="times new roman, serif">Make the right moves before the&nbsp;sales&nbsp;rush!&nbsp;</font>
            <span style="background-color:rgb(255,242,204)">
                <font size="4" face="times new roman, serif" color="#000000"><b style="">Book a&nbsp;<a href="https://calendly.com/shaishav-mahaseth/instadataworks-buybox-analysis" target="_blank" style="">slot</a>&nbsp;to know more.&nbsp;</b></font>
                <font face="georgia, serif" size="4"><b>
                        <font color="#000000" style="">&nbsp;</font>
                    </b><br>
                </font>
            </span>
        </p>
        <p></p>
        <div id="m_8418665251805808058m_7642596995947441409m_-6310540869815270074m_6922772992012954008gmail-craft_clipboard">
            <p style="font-variant-numeric:normal;font-variant-east-asian:normal;font-variant-alternates:normal;font-size-adjust:none;font-kerning:auto;font-feature-settings:normal;font-stretch:normal;line-height:22.5px;margin:0px;color:rgb(31,34,37)">
                <font size="4" face="times new roman, serif">Thanks,</font>
            </p>
            <p style="font-variant-numeric:normal;font-variant-east-asian:normal;font-variant-alternates:normal;font-size-adjust:none;font-kerning:auto;font-feature-settings:normal;font-stretch:normal;line-height:22.5px;margin:0px;color:rgb(31,34,37)">
                <font size="4">
                    <font face="times new roman, serif">Shai</font><br>
                </font><br>
            </p>
            <p style="font-variant-numeric:normal;font-variant-east-asian:normal;font-variant-alternates:normal;font-size-adjust:none;font-kerning:auto;font-feature-settings:normal;font-stretch:normal;line-height:22.5px;font-family:&quot;.AppleSystemUIFont&quot;;margin:0px;color:rgb(31,34,37)">
                <span style="font-family:&quot;.SFNS-Bold&quot;">Shaishav Mahaseth</span>
            </p>
            <p style="font-variant-numeric:normal;font-variant-east-asian:normal;font-variant-alternates:normal;font-size-adjust:none;font-kerning:auto;font-feature-settings:normal;font-stretch:normal;line-height:22.5px;font-family:&quot;.AppleSystemUIFont&quot;;margin:0px;color:rgb(31,34,37)">
                <span style="font-family:&quot;.SFNS-Regular&quot;">Co-Founder,&nbsp;</span><span style="font-family:&quot;.SFNS-Bold&quot;">InstaDataWorks</span>
            </p>
            <span style="font-family:'.SFNS-Regular';">Sub. of </span><span style="font-family:'.SFNS-Bold';">Acumensa Tech Pvt Ltd</span>
            <p style="font-variant-numeric:normal;font-variant-east-asian:normal;font-variant-alternates:normal;font-size-adjust:none;font-kerning:auto;font-feature-settings:normal;font-stretch:normal;line-height:22.5px;font-family:&quot;.AppleSystemUIFont&quot;;color:rgb(15,84,146);margin:0px">
                <span style="font-family:&quot;.SFNS-Regular&quot;;text-decoration-line:underline"><a href="https://instadata.works/" target="_blank">https://instadata.works/</a></span><br>
            </p>
            <span style="color:rgb(31,34,37);font-family:&quot;.SFNS-Regular&quot;">WhatsApp +91 7406447843</span><br>
            <p style="font-variant-numeric:normal;font-variant-east-asian:normal;font-variant-alternates:normal;font-size-adjust:none;font-kerning:auto;font-feature-settings:normal;font-stretch:normal;line-height:22.5px;font-family:&quot;.AppleSystemUIFont&quot;;margin:0px;color:rgb(31,34,37)">
                <span style="font-family:&quot;.SFNS-Regular&quot;">Salarpuria Symbiosis – Ground Floor, Begur Hobli,&nbsp;</span>
            </p>
            <p style="font-variant-numeric:normal;font-variant-east-asian:normal;font-variant-alternates:normal;font-size-adjust:none;font-kerning:auto;font-feature-settings:normal;font-stretch:normal;line-height:22.5px;font-family:&quot;.AppleSystemUIFont&quot;;margin:0px;color:rgb(31,34,37)">
                <span style="font-family:&quot;.SFNS-Regular&quot;">Bannerghatta Main Rd Bengaluru 560076</span>
            </p>
            <p style="font-variant-numeric:normal;font-variant-east-asian:normal;font-variant-alternates:normal;font-size-adjust:none;font-kerning:auto;font-feature-settings:normal;font-stretch:normal;font-size:15px;line-height:22.5px;font-family:&quot;.AppleSystemUIFont&quot;;margin:0px;color:rgb(31,34,37)">
                <img src="https://attachment.outlook.live.net/owa/MSA%3Adibyajyoti49%40outlook.com/service.svc/s/GetAttachmentThumbnail?id=AQMkADAwATM3ZmYAZS1lMGVmLTFkNDItMDACLTAwCgBGAAADmqoZYcj7oU2CEhmkLfH1UwcA6N7q5qkeH0Ohg7TBzgfqfAAAAgEMAAAA6N7q5qkeH0Ohg7TBzgfqfAAH%2FLvKPgAAAAESABAAYpkOgCW380qtfcbJs0RNsA%3D%3D&thumbnailType=2&isc=1&token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IkxsMDl3Zkc3em9Jc3JyZkFidGhsdUdGZXpGaz0iLCJ4NXQiOiJMbDA5d2ZHN3pvSXNycmZBYnRobHVHRmV6Rms9Iiwibm9uY2UiOiJFcXJJbTFxUXhFRVVNTGRkT3hRTWNUVC1OenFFX2tUYmg2SkdHRnV1XzcySFlqSmZTTS01YXRpVHNHZGV6ZFFrd1c4WkloanpsMTRRRVZHR1luMXVaN21aZHZ3aUVac3MtSm11alhPM1VvTHRPV0lwMGdnVUJ1SWFlN2pFZkpnVjhYSUs5dHlJMG8xTzIzWVZsYTltVGNraURRcHVqVl96LWZuZEZHZVFhM3MiLCJpc3Nsb2MiOiJTQTFQMjIzTUIxMDcwIiwic3JzbiI6NjM4ODA5MDk4OTczODMxMzQxfQ.eyJzYXAtdmVyc2lvbiI6IjMxIiwiYXBwaWQiOiJhZjNlYmJiYS1jMjNmLTQ5MmEtYWE5My04MzQyMTY5NmVjNGIiLCJpc3NyaW5nIjoiV1ciLCJhcHBpZGFjciI6IjIiLCJhcHBfZGlzcGxheW5hbWUiOiIiLCJ1dGkiOiI1YzhjNmUwNS1jYmMzLTRjN2EtYmQ2Ni1kYjhiOGI2YzlmOWYiLCJpYXQiOjE3NDU1MTUyMjAsInZlciI6IlNUSS5Vc2VyLkNhbGxiYWNrVG9rZW4uVjEiLCJ0aWQiOiI4NGRmOWU3ZmU5ZjY0MGFmYjQzNWFhYWFhYWFhYWFhYSIsInRydXN0ZWRmb3JkZWxlZ2F0aW9uIjoiZmFsc2UiLCJ0b3BvbG9neSI6IntcIlR5cGVcIjpcIk1hY2hpbmVcIixcIlZhbHVlXCI6XCJTQTFQMjIzTUIxMDcwLk5BTVAyMjMuUFJPRC5PVVRMT09LLkNPTVwifSIsInJlcXVlc3Rvcl9hcHBpZCI6IjE1N2NkZmJmLTczOTgtNGE1Ni05NmMzLWU5M2U5YWIzMDliNSIsInJlcXVlc3Rvcl9hcHBfZGlzcGxheW5hbWUiOiJPZmZpY2UgMzY1IEV4Y2hhbmdlIE1pY3Jvc2VydmljZSIsInNjcCI6Ik93YUF0dGFjaG1lbnRzLlJlYWQiLCJvaWQiOiIwMDAzN2ZmZS1lMGVmLTFkNDItMDAwMC0wMDAwMDAwMDAwMDAiLCJwdWlkIjoiMDAwMzdGRkVFMEVGMUQ0MiIsInNtdHAiOiJkaWJ5YWp5b3RpNDlAb3V0bG9vay5jb20iLCJ1cG4iOiJkaWJ5YWp5b3RpNDlAb3V0bG9vay5jb20iLCJ1c2VyY2FsbGJhY2t1c2VyY29udGV4dGlkIjoiMThhOGM4MzRkY2ZkNDc0Nzg1MmJmZmU0MTVkNTgxY2IiLCJlcGsiOiJ7XCJrdHlcIjpcIlJTQVwiLFwiblwiOlwic3pWbF9ZYlc5SkV0dDdIOU5lZ0pJdmNoeS1qUkpvNVpLSFlSelV5V2hkekplOC1JbktNZUtDV2ZjNXJFT1EyZ1B6QVh6SUNYd0ZqYjRnVnJwYXpTbjlFcDZPUFEzQ3k0TXZtcncxU0pvVGI0ZmVpdUtDUmlibVlVMTB0Y0s4V3g1dGROU203bGdROTN0Q3pkZWpheG9jRDZmeHhqMjhJRWppUElleTJ5SzhzSHZ0YW1PS1BmWnVwNmgyXzBRWXRMS1U0RUIxZFVfRnZvTEFGOUNnQ1E1ckU0ZjBZc3dDMWRvUldMbWl0OHBDWFFzRTVjdEl1cG9vN2V0bVJlRHc2U05ydmVkT012QUpIVW8xZk14NzFxYTlScU9aTG9UR09qM1hfRklXbWZma0JZc1Q1NklEY3ZyTmxTWnNnWEtaRU5QZG9yN2dqekxMMTNVMUdabzhfaEpRXCIsXCJlXCI6XCJBUUFCXCIsXCJhbGdcIjpcIlJTMjU2XCIsXCJleHBcIjpcIjE3NDU2MDQ3NjhcIixcImV4cF9kaWZmXCI6XCI4NjQwMFwiLFwia2lkXCI6XCJIOF9EdDI0cHJRVEVDbnFXUmpmUHl2RGVjcE1cIn0uZHlsSHhvZVBBMWZXVFVETWQ0Zk9pL1o2bWIrdFNHN3ptMGdYaGFYSnI2d1h4NzVCeG5VZ29Vcmc0ZWNxS05maHlXcWlWSTc0SzRrVm1TY3ZIV3VWbW9jaXdYQU5uaFhRM1FOaGJ4ZXZ3VjF4dHdmNFhKM0pPWWxMWEhnUW5HL2U0VExNaGVRanlDN0VSQnhWcVM1UXhHYXd4Zno5WEtnUjhveHBtTUxTZDFoSVhHaGxaL20xTkU0UVhKOHJzN3NscVppcG9HMlgvZGdML3BUNzhVeUFmWHUwYXJ3UFVYbHluK3ZHa2ZhVEIzKzdpWFlQZXlrNHhxenV2WEwzOGpWTHVLanJlR3pJbzc5TFNCS3hLUXBQVUlYZWhUd2daOEtKeFBLMkxBKzhhMkpmRUZ1cDBEQTRML2l6ZXNFS3h3dHdXQnNrSCtVRWhpRCs0Q08vbE5OS3BRPT0iLCJuYmYiOjE3NDU1MTUyMjAsImV4cCI6MTc0NTUxNTUyMCwiaXNzIjoiaHR0cHM6Ly9zdWJzdHJhdGUub2ZmaWNlLmNvbS9zdHMvIiwiYXVkIjoiaHR0cHM6Ly9vdXRsb29rLm9mZmljZS5jb20iLCJzc2VjIjoiRTdnL2JDV2FBbkZqL3ZHMSJ9.SlxwppZSc5Os0m0kQPmjQRPsAXjm2TPQL-TRZgFazu5GCbbWfHJA5DlrUTauLY1-G6CdvKO5QDs72VKVHg_NH3piCN_NfjHD-s9DwzcKUX24IOUZ-iDVj0wGkuz4gFrxCdOlQ7ZSPeP36rnipgc3TZI6aFOpiPLoLaG3TanWSCvN5d0M4omOjwLoTbrJHZ02fg1EnD1HjSWHwgiiARJQbvp5f0ysP3QRSY4za7-N6Q8EouTZpIgVeRLb72OEfjn_095CRsfCmSliRgam96dyzniPCbY4nzYM_t2mpl93Rt9TVrLxoqdWp6iGYIeGweP1jSe8L-07DttrwWJVcaJccg&X-OWA-CANARY=wTQ4TRWKcmYAAAAAAAAAACCmRGVQg90YtJtfgQRI6aBdDiZhO8O5uSf_MvCpN4DpuSgk0FymmjE.&owa=outlook.live.com&scriptVer=20250418009.05&clientId=C28D340D34234ED8AD88987971A4E23A&animation=true" alt="image.png" width="74" height="44" class="gmail-CToWUd" style="font-family: Arial, Helvetica, sans-serif; font-size: small; color: rgb(34, 34, 34); margin-right: 0px;">
            </p>
        </div>
    </div>
</body>

</html>
    """

    msg = MIMEMultipart()
    msg["Subject"] = SUBJECT
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(TO_EMAIL)
    # msg["Cc"] = ", ".join(CC_EMAIL)
    msg["Bcc"] = ", ".join(BCC_EMAIL)

    # Attach the Excel file
    with open(EXCEL_FILE_PATH, "rb") as file:
        part = MIMEApplication(file.read(), Name=os.path.basename(EXCEL_FILE_PATH))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(EXCEL_FILE_PATH)}"'
        msg.attach(part)
    # Attach HTML content
    msg.attach(MIMEText(html_template, "html"))

    # Send the email
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            # server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


async def run(seller_name, EXCEL_FILE_PATH):
    excel_insights = get_insights_from_excel(EXCEL_FILE_PATH)
    print(excel_insights)
    # send_mail(seller_name, excel_insights["winning_asin_count"], excel_insights["loosing_asin_count"],
    #           excel_insights["lost_due_to_price_count"],
    #           excel_insights["lost_due_to_rating_count"], excel_insights["lost_due_to_delivery_speed_count"],
    #           EXCEL_FILE_PATH, excel_insights["date"])
