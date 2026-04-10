import React from "react";

const tags = ["대구대", "하양", "추가예정"];

export default function QuickTags({ onSearch }) {
    // tag별 검색어를 정의
    const getSearchQuery = (tag) => {
        if (tag === "대구대" || tag === "하양") return `${tag} 맛집`;
        return tag;
    };

    return (
        <div className="quick-tags">
            {tags.map((tag) => (
                <button
                    key={tag}
                    onClick={
                        tag !== "추가예정"
                            ? () => onSearch(getSearchQuery(tag))
                            : undefined
                    }
                    disabled={tag === "추가예정"}
                    style={
                        tag === "추가예정"
                            ? { opacity: 0.6, cursor: "not-allowed" }
                            : {}
                    }
                >
                    {tag}
                </button>
            ))}
        </div>
    );
}
