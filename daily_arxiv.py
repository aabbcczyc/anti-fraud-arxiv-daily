# -*- coding: utf-8 -*-
import os
import re
import json
import arxiv
import yaml
import logging
import argparse
import datetime
import requests

logging.basicConfig(
    format='[%(asctime)s %(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)

base_url = "https://arxiv.paperswithcode.com/api/v0/papers/"
github_url = "https://api.github.com/search/repositories"
arxiv_url = "http://arxiv.org/"

def load_config(config_file: str) -> dict:
    def pretty_filters(**config) -> dict:
        keywords = dict()
        QUOTA = '"'
        OR = ' OR '
        def parse_filters(filters: list):
            return OR.join([f"{QUOTA}{f}{QUOTA}" for f in filters])
        for k, v in config['keywords'].items():
            keywords[k] = parse_filters(v['filters'])
        return keywords

    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
        config['kv'] = pretty_filters(**config)
        logging.info(f'加载配置: {config}')
    return config

def get_authors(authors, first_author=False):
    return authors[0] if first_author else ", ".join(str(a) for a in authors)

def sort_papers(papers):
    return dict(sorted(papers.items(), key=lambda x: x[0], reverse=True))

def get_code_link(qword: str) -> str:
    params = {"q": qword, "sort": "stars", "order": "desc"}
    try:
        response = requests.get(github_url, params=params).json()
        return response["items"][0]["html_url"] if response["total_count"] > 0 else None
    except:
        return None

def get_daily_papers(topic: str, query: str, max_results: int):
    content = {}
    content_web = {}
    
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    
    for result in search.results():
        paper_id = result.get_short_id()
        paper_key = paper_id.split('v')[0]
        
        try:
            repo_url = get_code_link(f"{result.title} {paper_key}")
            domain_tags = [k for k, v in config['keywords'].items() if any(f in result.title for f in v['filters'])]
            
            content[paper_key] = {
                "标题": result.title,
                "作者": get_authors(result.authors),
                "摘要": result.summary.replace("\n", " "),
                "日期": result.published.strftime("%Y-%m-%d"),
                "领域标签": domain_tags,
                "论文链接": f"{arxiv_url}abs/{paper_key}",
                "代码链接": repo_url
            }
            
            content_web[paper_key] = {
                "标题": result.title,
                "作者": get_authors(result.authors),
                "日期": result.published.strftime("%Y-%m-%d"),
                "领域": " | ".join(domain_tags),
                "论文": f"[PDF]({arxiv_url}abs/{paper_key})",
                "代码": f"[Code]({repo_url})" if repo_url else "无"
            }
            
            logging.info(f"发现论文: {result.title} [{', '.join(domain_tags)}]")
            
        except Exception as e:
            logging.error(f"处理论文 {paper_id} 时出错: {e}")
            
    return {topic: content}, {topic: content_web}

def update_json_file(filename, data_dict):
    with open(filename, "r", encoding='utf-8') as f:
        existing_data = json.load(f) if os.path.getsize(filename) > 0 else {}
    
    for data in data_dict:
        for topic, papers in data.items():
            if topic in existing_data:
                existing_data[topic].update(papers)
            else:
                existing_data[topic] = papers
    
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

def json_to_md(filename, md_filename, use_title=True, show_badge=True):
    with open(filename, "r", encoding='utf-8') as f:
        data = json.load(f) if os.path.getsize(filename) > 0 else {}
    
    with open(md_filename, "w", encoding='utf-8') as f:
        f.write(f"## 反欺诈/风控领域最新论文日报 - {datetime.date.today().strftime('%Y年%m月%d日')}\n\n")
        
        if show_badge:
            f.write("[![GitHub stars](https://img.shields.io/github/stars/aabbcczyc/anti-fraud-arxiv-daily?style=social)](https://github.com/aabbcczyc/anti-fraud-arxiv-daily)\n\n")
        
        f.write("### 论文目录\n")
        for topic in data.keys():
            f.write(f"- [{topic}](#{topic.lower().replace(' ', '-')})\n")
        
        for topic, papers in data.items():
            f.write(f"\n#### {topic}\n")
            f.write("| 发布日期 | 论文标题 | 作者 | 领域标签 | 论文链接 | 代码链接 |\n")
            f.write("|----------|----------|------|----------|----------|----------|\n")
            
            for paper in sorted(papers.values(), key=lambda x: x['日期'], reverse=True):
                f.write(
                    f"| {paper['日期']} | {paper['标题']} | {paper['作者']} | "
                    f"{' | '.join(paper['领域标签'])} | [PDF]({paper['论文链接']}) | "
                    f"[代码]({paper['代码链接']})|\n"
                )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config_path', type=str, default='config.yaml', help='配置文件路径')
    args = parser.parse_args()
    
    config = load_config(args.config_path)
    data_collector = []
    
    for topic, keyword in config['kv'].items():
        logging.info(f"开始获取 [{topic}] 领域论文")
        data, _ = get_daily_papers(topic, query=keyword, max_results=config['max_results'])
        data_collector.append(data)
    
    if config['publish_readme']:
        update_json_file(config['json_readme_path'], data_collector)
        json_to_md(
            config['json_readme_path'],
            config['md_readme_path'],
            show_badge=config['show_badge']
        )
    
    if config['publish_gitpage']:
        update_json_file(config['json_gitpage_path'], data_collector)
        json_to_md(
            config['json_gitpage_path'],
            config['md_gitpage_path'],
            show_badge=config['show_badge']
        )

if __name__ == "__main__":
    main()
