# Cults3D Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/HallyAus/Cults3D)](https://github.com/HallyAus/Cults3D/releases)
[![License](https://img.shields.io/github/license/HallyAus/Cults3D)](LICENSE)

A Home Assistant custom integration that connects to your [Cults3D](https://cults3d.com) account and provides comprehensive sensors for your creator profile statistics, sales tracking, and trending models.

## Features

### Profile Statistics
- **Followers Count** - Track how many people are following you
- **Following Count** - See how many creators you're following
- **Creations Count** - Monitor your total number of 3D model uploads
- **Total Views** - Track total views across all your designs

### Sales & Earnings
- **Total Earnings** - Your all-time earnings from sales (EUR)
- **Total Sales** - Number of sales across all time
- **Monthly Earnings** - Earnings from the last 30 days (EUR)
- **Monthly Sales** - Number of sales in the last 30 days

### Featured Creations
- **Latest Creation** - Your most recently published design
- **Top Downloaded (Trending)** - Your most downloaded design
- **Most Profitable** - Your highest-earning design

All data is fetched efficiently using a single GraphQL API call per update cycle (default: every 15 minutes).

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL: `https://github.com/HallyAus/Cults3D`
5. Select "Integration" as the category
6. Click "Add"
7. Search for "Cults3D" in HACS and install it
8. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/HallyAus/Cults3D/releases)
2. Extract the `cults3d` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

### Getting Your API Key

1. Log in to your [Cults3D account](https://cults3d.com)
2. Go to **Settings** > **API** (or visit [https://cults3d.com/en/settings/api](https://cults3d.com/en/settings/api))
3. Generate a new API key
4. Copy the API key - you'll need it for the integration setup

### Adding the Integration

1. Go to **Settings** > **Devices & Services** in Home Assistant
2. Click **+ Add Integration**
3. Search for "Cults3D"
4. Enter your Cults3D username (your profile nickname, not email)
5. Enter your API key
6. Click **Submit**

## Sensors

The integration creates the following sensors:

### Profile Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.cults3d_<username>_followers` | Number of followers | followers |
| `sensor.cults3d_<username>_following` | Number of people you follow | following |
| `sensor.cults3d_<username>_creations` | Total number of creations | creations |
| `sensor.cults3d_<username>_total_views` | Total views across all designs | views |

### Sales Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.cults3d_<username>_total_sales_amount` | All-time earnings | EUR |
| `sensor.cults3d_<username>_total_sales_count` | All-time number of sales | sales |
| `sensor.cults3d_<username>_monthly_sales_amount` | Earnings in last 30 days | EUR |
| `sensor.cults3d_<username>_monthly_sales_count` | Sales in last 30 days | sales |

### Creation Sensors

| Sensor | Description | Attributes |
|--------|-------------|------------|
| `sensor.cults3d_<username>_latest_creation` | Most recently published design | `url`, `image_url`, `views`, `downloads`, `likes`, `sales_amount`, `sales_count` |
| `sensor.cults3d_<username>_top_downloaded` | Most downloaded design (trending) | `url`, `image_url`, `views`, `downloads`, `likes`, `sales_amount`, `sales_count` |
| `sensor.cults3d_<username>_most_profitable` | Highest-earning design | `url`, `image_url`, `views`, `downloads`, `likes`, `sales_amount`, `sales_count` |

## Example Automations

### Notify on New Sale

```yaml
automation:
  - alias: "Cults3D New Sale Notification"
    trigger:
      - platform: state
        entity_id: sensor.cults3d_username_monthly_sales_count
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
    action:
      - service: notify.mobile_app
        data:
          title: "New Cults3D Sale!"
          message: "You made a sale! Monthly earnings: €{{ states('sensor.cults3d_username_monthly_sales_amount') }}"
```

### Notify When Follower Count Changes

```yaml
automation:
  - alias: "Cults3D Follower Notification"
    trigger:
      - platform: state
        entity_id: sensor.cults3d_username_followers
    condition:
      - condition: template
        value_template: "{{ trigger.from_state.state != trigger.to_state.state }}"
    action:
      - service: notify.mobile_app
        data:
          title: "Cults3D Update"
          message: "You now have {{ states('sensor.cults3d_username_followers') }} followers!"
```

### Dashboard Card Example

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Cults3D Profile
    entities:
      - entity: sensor.cults3d_username_followers
        name: Followers
      - entity: sensor.cults3d_username_following
        name: Following
      - entity: sensor.cults3d_username_creations
        name: Creations
      - entity: sensor.cults3d_username_total_views
        name: Total Views

  - type: entities
    title: Cults3D Earnings
    entities:
      - entity: sensor.cults3d_username_total_sales_amount
        name: Total Earnings
      - entity: sensor.cults3d_username_total_sales_count
        name: Total Sales
      - entity: sensor.cults3d_username_monthly_sales_amount
        name: Monthly Earnings
      - entity: sensor.cults3d_username_monthly_sales_count
        name: Monthly Sales

  - type: entities
    title: Featured Designs
    entities:
      - entity: sensor.cults3d_username_latest_creation
        name: Latest
      - entity: sensor.cults3d_username_top_downloaded
        name: Trending
      - entity: sensor.cults3d_username_most_profitable
        name: Most Profitable
```

## Troubleshooting

### Invalid Authentication Error

- Verify your username is your Cults3D **nickname** (shown in your profile URL), not your email
- Ensure your API key is correct and hasn't been regenerated
- Check that your API key has the necessary permissions

### User Not Found

- Make sure you're using your exact Cults3D username (case-sensitive)
- Verify your profile is public and accessible

### Sales Data Shows Zero

- Sales data requires the `myself` GraphQL query which needs proper API authentication
- If the full query fails, the integration falls back to public data only
- Check the Home Assistant logs for any authentication warnings

### Rate Limiting

The integration polls every 15 minutes by default to be respectful of the Cults3D API. If you experience rate limiting issues, you may need to increase the update interval by modifying `const.py`.

## GraphQL Schema Notes

This integration queries the Cults3D GraphQL API. The queries are defined in `coordinator.py` and can be adjusted if the schema changes:

```graphql
query GetFullUserData($nick: String!, $thirtyDaysAgo: ISO8601DateTime) {
  user(nick: $nick) {
    nick
    followersCount
    followeesCount
    creationsCount
    viewsCount

    # Creations sorted by different criteria
    latestCreation: creations(limit: 1, sort: BY_PUBLICATION, direction: DESC) { ... }
    topByDownloads: creations(limit: 1, sort: BY_DOWNLOADS, direction: DESC) { ... }
    topBySales: creations(limit: 1, sort: BY_SALES, direction: DESC) { ... }
  }

  myself {
    totalSalesAmount
    salesCount
    monthlySales: salesBatch(limit: 100, since: $thirtyDaysAgo) { ... }
  }
}
```

If you need to adjust the query for schema changes, edit the `CULTS3D_FULL_QUERY` or `CULTS3D_PUBLIC_QUERY` constants in `coordinator.py`.

## Support the Project

If you find this integration useful, consider buying me a coffee!

<a href="https://buymeacoffee.com/printforge" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not officially affiliated with or endorsed by Cults3D. Use at your own risk.
