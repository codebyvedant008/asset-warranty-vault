/* =========================================================
   ASSET & WARRANTY VAULT
   FRONTEND APPLICATION
   ========================================================= */


/* =========================================================
   GLOBAL STATE
   ========================================================= */

let assets = [];

let editingAssetId = null;


/* =========================================================
   DOM HELPERS
   ========================================================= */

function getElement(id) {
    return document.getElementById(id);
}


/* =========================================================
   NAVIGATION
   ========================================================= */

const dashboardNav = getElement("dashboardNav");
const assetsNav = getElement("assetsNav");
const addAssetNav = getElement("addAssetNav");

const dashboardSection = getElement("dashboardSection");
const assetsSection = getElement("assetsSection");
const addAssetSection = getElement("addAssetSection");

const pageTitle = getElement("pageTitle");
const pageSubtitle = getElement("pageSubtitle");

const addAssetButton = getElement("addAssetButton");
const assetsAddButton = getElement("assetsAddButton");
const emptyAddButton = getElement("emptyAddButton");
const viewAllButton = getElement("viewAllButton");


function setActiveNav(activeButton) {

    document.querySelectorAll(".nav-item").forEach(button => {
        button.classList.remove("active");
    });

    if (activeButton) {
        activeButton.classList.add("active");
    }
}


function showDashboard() {

    dashboardSection.style.display = "block";
    assetsSection.style.display = "none";
    addAssetSection.style.display = "none";

    pageTitle.textContent = "Dashboard";
    pageSubtitle.textContent =
        "Overview of your assets and warranties";

    setActiveNav(dashboardNav);

    updateDashboard();
}


function showAssets() {

    dashboardSection.style.display = "none";
    assetsSection.style.display = "block";
    addAssetSection.style.display = "none";

    pageTitle.textContent = "My Assets";
    pageSubtitle.textContent =
        "Manage all your registered assets";

    setActiveNav(assetsNav);

    renderAllAssets();
}


function showAddAsset(asset = null) {

    dashboardSection.style.display = "none";
    assetsSection.style.display = "none";
    addAssetSection.style.display = "block";

    setActiveNav(addAssetNav);

    const form = getElement("assetForm");

    form.reset();

    editingAssetId = null;

    getElement("selectedFileName").textContent =
        "No file selected";

    getElement("ocrStatus").textContent = "";

    if (asset) {

        editingAssetId = asset.id;

        pageTitle.textContent = "Edit Asset";
        pageSubtitle.textContent =
            "Update your asset information";

        getElement("productName").value =
            asset.product_name || "";

        getElement("brand").value =
            asset.brand || "";

        getElement("modelNumber").value =
            asset.model_number || "";

        getElement("serialNumber").value =
            asset.serial_number || "";

        getElement("purchaseDate").value =
            asset.purchase_date || "";

        getElement("purchasePrice").value =
            asset.purchase_price ?? "";

        getElement("currency").value =
            asset.currency || "INR";

        getElement("warrantyMonths").value =
            asset.warranty_months ?? "";

        getElement("seller").value =
            asset.seller || "";

        getElement("invoiceNumber").value =
            asset.invoice_number || "";

    } else {

        pageTitle.textContent = "Add Asset";
        pageSubtitle.textContent =
            "Register a new asset and warranty";

    }
}


dashboardNav.addEventListener(
    "click",
    showDashboard
);

assetsNav.addEventListener(
    "click",
    showAssets
);

addAssetNav.addEventListener(
    "click",
    () => showAddAsset()
);

addAssetButton.addEventListener(
    "click",
    () => showAddAsset()
);

assetsAddButton.addEventListener(
    "click",
    () => showAddAsset()
);

emptyAddButton.addEventListener(
    "click",
    () => showAddAsset()
);

viewAllButton.addEventListener(
    "click",
    showAssets
);


/* =========================================================
   LOAD ASSETS
   ========================================================= */

async function loadAssets() {

    try {

        const response =
            await fetch("/assets");

        if (!response.ok) {
            throw new Error(
                "Failed to load assets."
            );
        }

        assets = await response.json();

        updateDashboard();

        renderAllAssets();

    } catch (error) {

        console.error(
            "Asset loading error:",
            error
        );

    }
}


/* =========================================================
   DASHBOARD
   ========================================================= */

function updateDashboard() {

    const total =
        assets.length;

    const active =
        assets.filter(
            asset =>
                getWarrantyStatus(asset) === "active"
        ).length;

    const expiring =
        assets.filter(
            asset =>
                getWarrantyStatus(asset) === "expiring"
        ).length;

    const expired =
        assets.filter(
            asset =>
                getWarrantyStatus(asset) === "expired"
        ).length;

    const totalValue =
        assets.reduce(
            (sum, asset) =>
                sum + Number(asset.purchase_price || 0),
            0
        );


    getElement("totalAssets").textContent =
        total;

    getElement("activeWarranties").textContent =
        active;

    getElement("expiringSoon").textContent =
        expiring;

    getElement("totalValue").textContent =
        formatCurrency(totalValue);


    renderRecentAssets();

    renderWarrantyAlerts();

    renderAnalytics();
}


/* =========================================================
   CURRENCY
   ========================================================= */

function formatCurrency(
    amount,
    currency = "INR"
) {

    const symbols = {
        INR: "₹",
        USD: "$",
        EUR: "€",
        GBP: "£"
    };

    const symbol =
        symbols[currency] || currency;

    return (
        symbol +
        Number(amount || 0).toLocaleString(
            "en-IN",
            {
                maximumFractionDigits: 2
            }
        )
    );
}


/* =========================================================
   WARRANTY STATUS
   ========================================================= */

function getWarrantyStatus(asset) {

    if (!asset.warranty_expiry) {
        return "expired";
    }

    const expiry =
        new Date(
            asset.warranty_expiry + "T23:59:59"
        );

    const now =
        new Date();

    const diff =
        expiry.getTime() - now.getTime();

    const days =
        Math.ceil(
            diff / (1000 * 60 * 60 * 24)
        );


    if (days < 0) {
        return "expired";
    }

    if (days <= 30) {
        return "expiring";
    }

    return "active";
}


function getDaysRemaining(asset) {

    if (!asset.warranty_expiry) {
        return null;
    }

    const expiry =
        new Date(
            asset.warranty_expiry + "T23:59:59"
        );

    const now =
        new Date();

    return Math.ceil(
        (
            expiry.getTime() -
            now.getTime()
        ) /
        (1000 * 60 * 60 * 24)
    );
}


/* =========================================================
   RECENT ASSETS
   ========================================================= */

function renderRecentAssets() {

    const grid =
        getElement("assetGrid");

    const emptyState =
        getElement("emptyState");


    if (!assets.length) {

        grid.innerHTML = "";

        emptyState.style.display =
            "block";

        return;

    }


    emptyState.style.display =
        "none";


    const recentAssets =
        [...assets]
            .sort(
                (a, b) =>
                    new Date(b.created_at) -
                    new Date(a.created_at)
            )
            .slice(0, 4);


    grid.innerHTML =
        recentAssets
            .map(
                asset =>
                    createAssetCard(asset)
            )
            .join("");
}


/* =========================================================
   ASSET CARD
   ========================================================= */

function createAssetCard(asset) {

    const status =
        getWarrantyStatus(asset);

    const days =
        getDaysRemaining(asset);

    const statusText = {

        active: "Active",

        expiring: "Expiring Soon",

        expired: "Expired"

    }[status];


    const statusClass =
        `status-${status}`;


    const progress =
        calculateWarrantyProgress(asset);


    return `

        <div class="asset-card">

            <div class="asset-card-top">

                <div class="asset-card-icon">
                    ◫
                </div>

                <span class="warranty-badge ${statusClass}">
                    ${statusText}
                </span>

            </div>


            <h3>
                ${escapeHtml(
                    asset.product_name || "Unnamed Asset"
                )}
            </h3>


            <p class="asset-brand">
                ${escapeHtml(
                    asset.brand || "Unknown Brand"
                )}
            </p>


            <div class="asset-card-details">

                <div>

                    <span>
                        Purchase
                    </span>

                    <strong>
                        ${formatDate(
                            asset.purchase_date
                        )}
                    </strong>

                </div>


                <div>

                    <span>
                        Value
                    </span>

                    <strong>
                        ${formatCurrency(
                            asset.purchase_price,
                            asset.currency
                        )}
                    </strong>

                </div>

            </div>


            ${
                asset.warranty_expiry
                    ? `

                    <div class="warranty-progress-section">

                        <div class="warranty-progress-header">

                            <span>
                                Warranty
                            </span>

                            <span>
                                ${
                                    days >= 0
                                        ? `${days} days left`
                                        : "Expired"
                                }
                            </span>

                        </div>


                        <div class="warranty-progress">

                            <div
                                class="warranty-progress-bar ${statusClass}"
                                style="width: ${progress}%"
                            ></div>

                        </div>

                    </div>

                    `
                    : ""
            }


            <button
                type="button"
                class="asset-view-button"
                onclick="showAssetDetails(${asset.id})"
            >

                View Details

            </button>

        </div>

    `;
}


/* =========================================================
   WARRANTY PROGRESS
   ========================================================= */

function calculateWarrantyProgress(asset) {

    if (
        !asset.purchase_date ||
        !asset.warranty_expiry
    ) {
        return 0;
    }


    const start =
        new Date(
            asset.purchase_date
        );

    const end =
        new Date(
            asset.warranty_expiry
        );

    const now =
        new Date();


    const total =
        end.getTime() -
        start.getTime();

    const elapsed =
        now.getTime() -
        start.getTime();


    if (total <= 0) {
        return 0;
    }


    let percentage =
        100 -
        (
            elapsed / total
        ) *
        100;


    percentage =
        Math.max(
            0,
            Math.min(
                100,
                percentage
            )
        );


    return percentage;
}


/* =========================================================
   ALL ASSETS
   ========================================================= */

function renderAllAssets() {

    const grid =
        getElement("allAssetsGrid");


    if (!assets.length) {

        grid.innerHTML = `

            <div class="empty-state">

                <div class="empty-state-icon">
                    ◫
                </div>

                <h3>
                    No assets yet
                </h3>

                <p>
                    Add your first asset to start managing
                    warranties and receipts.
                </p>

            </div>

        `;

        return;
    }


    const searchInput =
        getElement("assetSearch");

    const filterInput =
        getElement("warrantyFilter");

    const sortInput =
        getElement("assetSort");


    const search =
        (
            searchInput?.value ||
            ""
        )
            .trim()
            .toLowerCase();


    const filter =
        filterInput?.value ||
        "all";


    const sort =
        sortInput?.value ||
        "newest";


    let filtered =
        assets.filter(
            asset => {

                const searchableText = [

                    asset.product_name,

                    asset.brand,

                    asset.model_number,

                    asset.serial_number,

                    asset.invoice_number,

                    asset.seller

                ]
                    .filter(Boolean)
                    .join(" ")
                    .toLowerCase();


                const matchesSearch =
                    !search ||
                    searchableText.includes(search);


                const status =
                    getWarrantyStatus(asset);


                const matchesFilter =
                    filter === "all" ||
                    status === filter;


                return (
                    matchesSearch &&
                    matchesFilter
                );
            }
        );


    filtered.sort(
        (a, b) => {

            switch (sort) {

                case "oldest":

                    return (
                        new Date(a.created_at) -
                        new Date(b.created_at)
                    );


                case "price-high":

                    return (
                        Number(b.purchase_price || 0) -
                        Number(a.purchase_price || 0)
                    );


                case "price-low":

                    return (
                        Number(a.purchase_price || 0) -
                        Number(b.purchase_price || 0)
                    );


                case "warranty-soon":

                    return (
                        new Date(
                            a.warranty_expiry ||
                            "9999-12-31"
                        ) -
                        new Date(
                            b.warranty_expiry ||
                            "9999-12-31"
                        )
                    );


                case "newest":

                default:

                    return (
                        new Date(b.created_at) -
                        new Date(a.created_at)
                    );

            }

        }
    );


    if (!filtered.length) {

        grid.innerHTML = `

            <div class="empty-state">

                <div class="empty-state-icon">
                    ⌕
                </div>

                <h3>
                    No matching assets
                </h3>

                <p>
                    Try changing your search or filters.
                </p>

            </div>

        `;

        return;
    }


    grid.innerHTML =
        filtered
            .map(
                asset =>
                    createAssetCard(asset)
            )
            .join("");
}


/* =========================================================
   SEARCH / FILTER / SORT
   ========================================================= */

const assetSearch =
    getElement("assetSearch");

const warrantyFilter =
    getElement("warrantyFilter");

const assetSort =
    getElement("assetSort");


if (assetSearch) {

    assetSearch.addEventListener(
        "input",
        renderAllAssets
    );

}


if (warrantyFilter) {

    warrantyFilter.addEventListener(
        "change",
        renderAllAssets
    );

}


if (assetSort) {

    assetSort.addEventListener(
        "change",
        renderAllAssets
    );

}


/* =========================================================
   WARRANTY ALERTS
   ========================================================= */

function renderWarrantyAlerts() {

    const container =
        getElement("warrantyAlerts");


    const attentionAssets =
        assets
            .map(
                asset => ({
                    asset,
                    days:
                        getDaysRemaining(asset)
                })
            )
            .filter(
                item =>
                    item.days !== null &&
                    item.days <= 30
            )
            .sort(
                (a, b) =>
                    a.days - b.days
            )
            .slice(0, 5);


    if (!attentionAssets.length) {

        container.innerHTML = `

            <div class="warranty-alert-empty">

                <div class="alert-success-icon">
                    ✓
                </div>

                <div>

                    <strong>
                        All warranties are on track
                    </strong>

                    <p>
                        No assets currently require attention.
                    </p>

                </div>

            </div>

        `;

        return;
    }


    container.innerHTML =
        attentionAssets
            .map(
                item => {

                    const asset =
                        item.asset;

                    const days =
                        item.days;


                    const isExpired =
                        days < 0;


                    return `

                        <div class="warranty-alert-item">

                            <div class="warranty-alert-icon">
                                !
                            </div>


                            <div class="warranty-alert-content">

                                <strong>
                                    ${escapeHtml(
                                        asset.product_name ||
                                        "Unnamed Asset"
                                    )}
                                </strong>

                                <p>

                                    ${
                                        isExpired
                                            ? `Warranty expired ${Math.abs(days)} days ago`
                                            : `Warranty expires in ${days} days`
                                    }

                                </p>

                            </div>


                            <button
                                type="button"
                                class="alert-view-button"
                                onclick="showAssetDetails(${asset.id})"
                            >

                                View

                            </button>

                        </div>

                    `;

                }
            )
            .join("");
}


/* =========================================================
   ANALYTICS
   ========================================================= */

function renderAnalytics() {

    renderWarrantyAnalytics();

    renderValueAnalytics();

    renderWarrantyTimeline();

    renderAssetInsights();
}


/* =========================================================
   WARRANTY ANALYTICS
   ========================================================= */

function renderWarrantyAnalytics() {

    const active =
        assets.filter(
            asset =>
                getWarrantyStatus(asset) === "active"
        ).length;


    const expiring =
        assets.filter(
            asset =>
                getWarrantyStatus(asset) === "expiring"
        ).length;


    const expired =
        assets.filter(
            asset =>
                getWarrantyStatus(asset) === "expired"
        ).length;


    const total =
        assets.length;


    getElement("analyticsActive").textContent =
        active;

    getElement("analyticsExpiring").textContent =
        expiring;

    getElement("analyticsExpired").textContent =
        expired;


    const activePercentage =
        total
            ? (active / total) * 100
            : 0;


    const expiringPercentage =
        total
            ? (expiring / total) * 100
            : 0;


    const expiredPercentage =
        total
            ? (expired / total) * 100
            : 0;


    getElement("activeBar").style.width =
        `${activePercentage}%`;

    getElement("expiringBar").style.width =
        `${expiringPercentage}%`;

    getElement("expiredBar").style.width =
        `${expiredPercentage}%`;
}


/* =========================================================
   VALUE ANALYTICS
   ========================================================= */

function renderValueAnalytics() {

    const values =
        assets
            .map(
                asset =>
                    Number(
                        asset.purchase_price || 0
                    )
            )
            .filter(
                value =>
                    value > 0
            );


    const totalValue =
        values.reduce(
            (sum, value) =>
                sum + value,
            0
        );


    const averageValue =
        values.length
            ? totalValue / values.length
            : 0;


    const highestValue =
        values.length
            ? Math.max(...values)
            : 0;


    getElement(
        "analyticsTotalValue"
    ).textContent =
        formatCurrency(
            totalValue
        );


    getElement(
        "analyticsAverageValue"
    ).textContent =
        formatCurrency(
            averageValue
        );


    getElement(
        "analyticsHighestValue"
    ).textContent =
        formatCurrency(
            highestValue
        );
}


/* =========================================================
   WARRANTY TIMELINE
   ========================================================= */

function renderWarrantyTimeline() {

    const container =
        getElement(
            "warrantyTimeline"
        );


    const timelineAssets =
        assets
            .filter(
                asset =>
                    asset.warranty_expiry
            )
            .map(
                asset => ({
                    asset,
                    days:
                        getDaysRemaining(asset)
                })
            )
            .sort(
                (a, b) =>
                    a.days - b.days
            )
            .slice(0, 6);


    if (!timelineAssets.length) {

        container.innerHTML = `

            <div class="analytics-empty">

                No warranty data available.

            </div>

        `;

        return;
    }


    container.innerHTML =
        timelineAssets
            .map(
                item => {

                    const asset =
                        item.asset;

                    const days =
                        item.days;


                    let statusText;

                    if (days < 0) {

                        statusText =
                            `Expired ${Math.abs(days)} days ago`;

                    } else if (days === 0) {

                        statusText =
                            "Expires today";

                    } else {

                        statusText =
                            `${days} days remaining`;

                    }


                    return `

                        <div class="timeline-item">

                            <div class="timeline-date">

                                <strong>
                                    ${formatShortDate(
                                        asset.warranty_expiry
                                    )}
                                </strong>

                            </div>


                            <div class="timeline-line">

                                <span></span>

                            </div>


                            <div class="timeline-content">

                                <strong>
                                    ${escapeHtml(
                                        asset.product_name ||
                                        "Unnamed Asset"
                                    )}
                                </strong>

                                <p>
                                    ${statusText}
                                </p>

                            </div>

                        </div>

                    `;

                }
            )
            .join("");
}


/* =========================================================
   ASSET INSIGHTS
   ========================================================= */

function renderAssetInsights() {

    const container =
        getElement(
            "assetInsights"
        );


    const valuableAssets =
        [...assets]
            .filter(
                asset =>
                    Number(
                        asset.purchase_price || 0
                    ) > 0
            )
            .sort(
                (a, b) =>
                    Number(
                        b.purchase_price || 0
                    ) -
                    Number(
                        a.purchase_price || 0
                    )
            )
            .slice(0, 5);


    if (!valuableAssets.length) {

        container.innerHTML = `

            <div class="analytics-empty">

                No assets available.

            </div>

        `;

        return;
    }


    container.innerHTML =
        valuableAssets
            .map(
                (asset, index) => `

                    <div class="insight-item">

                        <div class="insight-rank">

                            ${index + 1}

                        </div>


                        <div class="insight-info">

                            <strong>
                                ${escapeHtml(
                                    asset.product_name ||
                                    "Unnamed Asset"
                                )}
                            </strong>

                            <span>
                                ${escapeHtml(
                                    asset.brand ||
                                    "Unknown Brand"
                                )}
                            </span>

                        </div>


                        <strong class="insight-price">

                            ${formatCurrency(
                                asset.purchase_price,
                                asset.currency
                            )}

                        </strong>

                    </div>

                `
            )
            .join("");
}


/* =========================================================
   ASSET DETAILS MODAL
   ========================================================= */

function showAssetDetails(assetId) {

    const asset =
        assets.find(
            item =>
                item.id === assetId
        );


    if (!asset) {
        return;
    }


    const modal =
        getElement("assetModal");

    const body =
        getElement("modalBody");


    const status =
        getWarrantyStatus(asset);

    const days =
        getDaysRemaining(asset);


    const statusText = {

        active: "Active",

        expiring: "Expiring Soon",

        expired: "Expired"

    }[status];


    const receiptSection =
        asset.receipt_path
            ? `

                <div class="receipt-box">

                    <div class="receipt-icon">
                        📄
                    </div>

                    <div class="receipt-info">

                        <strong>
                            Receipt
                        </strong>

                        <span>
                            Receipt Uploaded
                        </span>

                    </div>

                    <div class="receipt-actions">

                        <button
                            type="button"
                            class="receipt-view-button"
                            onclick="viewReceipt(${asset.id})"
                        >

                            View Receipt

                        </button>

                        <button
                            type="button"
                            class="receipt-download-button"
                            onclick="downloadReceipt(${asset.id})"
                        >

                            Download

                        </button>

                    </div>

                </div>

            `
            : "";


    body.innerHTML = `

        <div class="modal-header">

            <div>

                <span class="modal-label">
                    Asset Details
                </span>

                <h2>
                    ${escapeHtml(
                        asset.product_name ||
                        "Unnamed Asset"
                    )}
                </h2>

                <p>
                    ${escapeHtml(
                        asset.brand ||
                        "Unknown Brand"
                    )}
                </p>

            </div>

            <span class="warranty-badge status-${status}">
                ${statusText}
            </span>

        </div>


        <div class="modal-details-grid">


            <div class="modal-detail">

                <span>
                    Model Number
                </span>

                <strong>
                    ${escapeHtml(
                        asset.model_number ||
                        "Not available"
                    )}
                </strong>

            </div>


            <div class="modal-detail">

                <span>
                    Serial Number
                </span>

                <strong>
                    ${escapeHtml(
                        asset.serial_number ||
                        "Not available"
                    )}
                </strong>

            </div>


            <div class="modal-detail">

                <span>
                    Purchase Date
                </span>

                <strong>
                    ${formatDate(
                        asset.purchase_date
                    )}
                </strong>

            </div>


            <div class="modal-detail">

                <span>
                    Purchase Price
                </span>

                <strong>
                    ${formatCurrency(
                        asset.purchase_price,
                        asset.currency
                    )}
                </strong>

            </div>


            <div class="modal-detail">

                <span>
                    Warranty Duration
                </span>

                <strong>
                    ${
                        asset.warranty_months
                            ? `${asset.warranty_months} months`
                            : "Not available"
                    }
                </strong>

            </div>


            <div class="modal-detail">

                <span>
                    Warranty Expiry
                </span>

                <strong>
                    ${formatDate(
                        asset.warranty_expiry
                    )}
                </strong>

            </div>


            <div class="modal-detail">

                <span>
                    Seller
                </span>

                <strong>
                    ${escapeHtml(
                        asset.seller ||
                        "Not available"
                    )}
                </strong>

            </div>


            <div class="modal-detail">

                <span>
                    Invoice Number
                </span>

                <strong>
                    ${escapeHtml(
                        asset.invoice_number ||
                        "Not available"
                    )}
                </strong>

            </div>

        </div>


        ${
            asset.warranty_expiry
                ? `

                    <div class="modal-warranty">

                        <div class="modal-warranty-header">

                            <span>
                                Warranty Progress
                            </span>

                            <strong>

                                ${
                                    days >= 0
                                        ? `${days} days remaining`
                                        : "Warranty expired"
                                }

                            </strong>

                        </div>


                        <div class="warranty-progress">

                            <div
                                class="warranty-progress-bar status-${status}"
                                style="width: ${calculateWarrantyProgress(asset)}%"
                            ></div>

                        </div>

                    </div>

                `
                : ""
        }


        ${receiptSection}


        <div class="modal-actions">

            <button
                type="button"
                class="secondary-button"
                onclick="editAsset(${asset.id})"
            >

                Edit Asset

            </button>


            <button
                type="button"
                class="delete-button"
                onclick="deleteAsset(${asset.id})"
            >

                Delete Asset

            </button>

        </div>

    `;


    modal.style.display =
        "flex";
}


getElement("modalClose").addEventListener(
    "click",
    () => {

        getElement(
            "assetModal"
        ).style.display = "none";

    }
);


getElement("assetModal").addEventListener(
    "click",
    event => {

        if (
            event.target ===
            getElement("assetModal")
        ) {

            getElement(
                "assetModal"
            ).style.display = "none";

        }

    }
);


/* =========================================================
   EDIT ASSET
   ========================================================= */

function editAsset(assetId) {

    const asset =
        assets.find(
            item =>
                item.id === assetId
        );


    if (!asset) {
        return;
    }


    getElement(
        "assetModal"
    ).style.display = "none";


    showAddAsset(asset);
}


/* =========================================================
   DELETE ASSET
   ========================================================= */

async function deleteAsset(assetId) {

    const asset =
        assets.find(
            item =>
                item.id === assetId
        );


    if (!asset) {
        return;
    }


    const confirmed =
        confirm(
            `Delete "${asset.product_name}"?`
        );


    if (!confirmed) {
        return;
    }


    try {

        const response =
            await fetch(
                `/assets/${assetId}`,
                {
                    method: "DELETE"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Failed to delete asset."
            );

        }


        getElement(
            "assetModal"
        ).style.display = "none";


        await loadAssets();


        alert(
            "Asset deleted successfully."
        );


    } catch (error) {

        console.error(error);

        alert(
            "Could not delete the asset."
        );

    }
}


/* =========================================================
   ASSET FORM
   ========================================================= */

getElement(
    "assetForm"
).addEventListener(
    "submit",
    async event => {

        event.preventDefault();


        const assetData = {

            product_name:
                getElement(
                    "productName"
                ).value.trim(),

            brand:
                getElement(
                    "brand"
                ).value.trim() || null,

            model_number:
                getElement(
                    "modelNumber"
                ).value.trim() || null,

            serial_number:
                getElement(
                    "serialNumber"
                ).value.trim() || null,

            purchase_date:
                getElement(
                    "purchaseDate"
                ).value || null,

            purchase_price:
                getElement(
                    "purchasePrice"
                ).value
                    ? Number(
                        getElement(
                            "purchasePrice"
                        ).value
                    )
                    : null,

            currency:
                getElement(
                    "currency"
                ).value,

            warranty_months:
                getElement(
                    "warrantyMonths"
                ).value
                    ? Number(
                        getElement(
                            "warrantyMonths"
                        ).value
                    )
                    : null,

            seller:
                getElement(
                    "seller"
                ).value.trim() || null,

            invoice_number:
                getElement(
                    "invoiceNumber"
                ).value.trim() || null

        };


        try {

            let response;


            if (editingAssetId) {

                response =
                    await fetch(
                        `/assets/${editingAssetId}`,
                        {
                            method: "PATCH",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify(
                                    assetData
                                )
                        }
                    );

            } else {

                response =
                    await fetch(
                        "/assets",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify(
                                    assetData
                                )
                        }
                    );

            }


            if (!response.ok) {

                const errorData =
                    await response.json()
                        .catch(
                            () => ({})
                        );

                throw new Error(
                    errorData.detail ||
                    "Failed to save asset."
                );

            }


            const savedAsset =
                await response.json();


            const selectedFile =
                getElement(
                    "receiptFile"
                ).files[0];


            if (
                selectedFile &&
                savedAsset.id
            ) {

                const formData =
                    new FormData();

                formData.append(
                    "file",
                    selectedFile
                );

                formData.append(
                    "asset_id",
                    savedAsset.id
                );


                const uploadResponse =
                    await fetch(
                        "/assets/upload-receipt",
                        {
                            method: "POST",
                            body: formData
                        }
                    );


                if (!uploadResponse.ok) {

                    console.warn(
                        "Asset saved but receipt upload failed."
                    );

                }

            }


            alert(
                editingAssetId
                    ? "Asset updated successfully."
                    : "Asset added successfully."
            );


            await loadAssets();

            showDashboard();


        } catch (error) {

            console.error(error);

            alert(
                error.message ||
                "Could not save the asset."
            );

        }

    }
);


/* =========================================================
   FILE UPLOAD
   ========================================================= */

getElement(
    "chooseFileButton"
).addEventListener(
    "click",
    () => {

        getElement(
            "receiptFile"
        ).click();

    }
);


getElement(
    "receiptFile"
).addEventListener(
    "change",
    event => {

        const file =
            event.target.files[0];


        getElement(
            "selectedFileName"
        ).textContent =
            file
                ? file.name
                : "No file selected";

    }
);


/* =========================================================
   OCR
   ========================================================= */

getElement(
    "scanButton"
).addEventListener(
    "click",
    async () => {

        const file =
            getElement(
                "receiptFile"
            ).files[0];


        if (!file) {

            alert(
                "Please choose an invoice image first."
            );

            return;
        }


        const status =
            getElement(
                "ocrStatus"
            );


        status.textContent =
            "Scanning invoice...";


        const formData =
            new FormData();

        formData.append(
            "file",
            file
        );


        try {

            const response =
                await fetch(
                    "/assets/upload-receipt",
                    {
                        method: "POST",
                        body: formData
                    }
                );


            if (!response.ok) {

                const errorData =
                    await response.json()
                        .catch(
                            () => ({})
                        );

                throw new Error(
                    errorData.detail ||
                    "OCR failed."
                );

            }


            const data =
                await response.json();


            const extracted =
                data.extracted_fields ||
                {};


            getElement(
                "productName"
            ).value =
                extracted.product_name || "";


            getElement(
                "brand"
            ).value =
                extracted.brand || "";


            getElement(
                "modelNumber"
            ).value =
                extracted.model_number || "";


            getElement(
                "serialNumber"
            ).value =
                extracted.serial_number || "";


            getElement(
                "purchaseDate"
            ).value =
                extracted.purchase_date || "";


            getElement(
                "purchasePrice"
            ).value =
                extracted.purchase_price ?? "";


            getElement(
                "currency"
            ).value =
                extracted.currency ||
                "INR";


            getElement(
                "warrantyMonths"
            ).value =
                extracted.warranty_months ?? "";


            getElement(
                "seller"
            ).value =
                extracted.seller || "";


            getElement(
                "invoiceNumber"
            ).value =
                extracted.invoice_number || "";


            status.textContent =
                "Invoice scanned successfully. Please review the extracted details.";

        } catch (error) {

            console.error(error);

            status.textContent =
                "OCR failed. Please enter the details manually.";

            alert(
                error.message ||
                "Could not scan the invoice."
            );

        }

    }
);


/* =========================================================
   CANCEL
   ========================================================= */

getElement(
    "cancelButton"
).addEventListener(
    "click",
    () => {

        showDashboard();

    }
);


/* =========================================================
   RECEIPT VIEW
   ========================================================= */

function viewReceipt(assetId) {

    const asset =
        assets.find(
            item =>
                item.id === assetId
        );


    if (!asset) {
        return;
    }


    if (!asset.receipt_path) {

        alert(
            "No receipt is available for this asset."
        );

        return;
    }


    const receiptUrl =
        `/assets/${assetId}/receipt`;


    window.open(
        receiptUrl,
        "_blank"
    );
}


/* =========================================================
   RECEIPT DOWNLOAD
   ========================================================= */

function downloadReceipt(assetId) {

    const asset =
        assets.find(
            item =>
                item.id === assetId
        );


    if (!asset) {
        return;
    }


    if (!asset.receipt_path) {

        alert(
            "No receipt is available for this asset."
        );

        return;
    }


    const downloadUrl =
        `/assets/${assetId}/receipt/download`;


    const link =
        document.createElement(
            "a"
        );


    link.href =
        downloadUrl;

    link.setAttribute(
        "download",
        ""
    );


    document.body.appendChild(
        link
    );


    link.click();

    link.remove();
}


/* =========================================================
   DATE HELPERS
   ========================================================= */

function formatDate(dateString) {

    if (!dateString) {
        return "Not available";
    }


    const date =
        new Date(
            dateString + "T00:00:00"
        );


    if (Number.isNaN(date.getTime())) {
        return "Not available";
    }


    return date.toLocaleDateString(
        "en-IN",
        {
            day: "2-digit",
            month: "short",
            year: "numeric"
        }
    );
}


function formatShortDate(dateString) {

    if (!dateString) {
        return "--";
    }


    const date =
        new Date(
            dateString + "T00:00:00"
        );


    if (Number.isNaN(date.getTime())) {
        return "--";
    }


    return date.toLocaleDateString(
        "en-IN",
        {
            day: "2-digit",
            month: "short"
        }
    );
}


/* =========================================================
   HTML ESCAPING
   ========================================================= */

function escapeHtml(value) {

    if (value === null || value === undefined) {
        return "";
    }


    return String(value)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );
}


/* =========================================================
   GLOBAL FUNCTIONS
   ========================================================= */

window.showAssetDetails =
    showAssetDetails;

window.editAsset =
    editAsset;

window.deleteAsset =
    deleteAsset;

window.viewReceipt =
    viewReceipt;

window.downloadReceipt =
    downloadReceipt;


/* =========================================================
   INITIAL LOAD
   ========================================================= */

loadAssets();
