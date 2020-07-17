from crawler.spiders.util import normalize_rating


def parse_details(details):
    """
    Parse the details from the Google Play api
    Args:
        details: dict
    """
    docv2 = details.docV2
    url = docv2.shareUrl
    pkg_name = docv2.docid
    app_name = docv2.title
    creator = docv2.creator
    description = docv2.descriptionHtml
    restriction = docv2.availability.restriction
    available = restriction == 1
    user_rating = docv2.aggregateRating.starRating
    user_rating = normalize_rating(user_rating, 5)

    ad = docv2.details.appDetails
    developer_name = ad.developerName
    developer_email = ad.developerEmail
    developer_website = ad.developerWebsite
    downloads = ad.numDownloads

    ann = docv2.annotations
    privacy_policy_url = ann.privacyPolicyUrl
    contains_ads = "contains ads" in ann.badgeForDoc

    offer = docv2.offer

    meta = dict(
        url=url,
        pkg_name=pkg_name,
        app_name=app_name,
        creator=creator,
        description=description,
        available=available,
        user_rating=user_rating,
        developer_name=developer_name,
        developer_email=developer_email,
        developer_website=developer_website,
        downloads=downloads,
        privacy_policy_url=privacy_policy_url,
        contains_ads=contains_ads,
        restriction=restriction
    )

    try:
        currency = offer[0].currencyCode
        price = offer[0].formattedAmount
        offer_type = offer[0].offerType

        meta["currency"] = currency
        meta["price"] = price
        meta["offer_type"] = offer_type
    except IndexError:
        pass

    version_code = ad.versionCode
    version_string = ad.versionString
    version_date = ad.uploadDate

    versions = {
        version_string: {
            "timestamp": version_date,
            "code": version_code
        }
    }
    return meta, versions
